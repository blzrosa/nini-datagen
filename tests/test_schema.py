"""Schema, table, lotes (scan) e os geradores que dependem de outra coluna."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from typing import Any, Literal

import numpy as np
import polars as pl
import pytest

import nini_datagen as dg
from nini_datagen.core.blocks import BLOCK_ROWS
from nini_datagen.providers.base import Context
from nini_datagen.registry import registry
from nini_datagen.schema import iter_batches, scan_source

from .helpers import CASES, case

FAKE = getattr(pl, "IS_FAKE", False)
SEED = 77
N = BLOCK_ROWS + 500  # dois blocos, o segundo incompleto
ON = dt.date(2026, 1, 1)


def people_schema() -> dg.Schema:
    return dg.Schema({
        "id": ("cpf", {"unique": True, "formatted": True}),
        "sexo": "sex",
        "nome": ("first_name", {"sex": dg.ref("sexo")}),
        "completo": ("full_name", {"sex": dg.ref("sexo"), "null_fraction": 0.1}),
        "idade": ("age", {"low": 18, "high": 90}),
        "nascimento": ("birthdate", {"age": dg.ref("idade"), "on": ON}),
        "renda": ("correlated", {"other": dg.ref("idade"), "rho": 0.5, "mean": 8, "std": 0.6, "lognormal": True}),
        "area": ("choice_by", {"by": dg.ref("sexo"), "options": {"F": ["a", "b"], "M": (["c", "d"], [1, 3])}}),
        "ativo": ("boolean", {"p": 0.8}),
        "meses": pl.col("idade") * 12,
    })  # fmt: skip


def ctx(seed: int = SEED, threads: int | None = None) -> Context:
    g = dg.DataGen(seed=seed, threads=threads)
    return g._ctx


def concat_lists(frames: list[pl.DataFrame], name: str) -> list:
    return [v for f in frames for v in f[name].to_list()]


# ----------------------------------------------------------------------------- geração a partir de um bloco
@pytest.mark.parametrize("name", sorted(CASES))
def test_generate_from_offset_matches_full(name: str) -> None:
    """Gerar a partir do bloco 1 dá exatamente as linhas seguintes da coluna gerada de uma vez (base dos lotes)."""
    kind, kw = case(name)
    provider = registry.get(kind)
    cfg = registry.config(kind, None, null_fraction=0.1, **kw)
    c = ctx()
    full = provider.generate(N, cfg, c).to_list()
    first = provider.generate(BLOCK_ROWS, cfg, c, None, 0).to_list()
    rest = provider.generate(N - BLOCK_ROWS, cfg, c, None, 1).to_list()
    assert first + rest == full


# ----------------------------------------------------------------------------- table
def test_table_columns_match_standalone() -> None:
    g = dg.DataGen(seed=SEED)
    df = g.table(N, people_schema())
    assert df.columns == ["id", "sexo", "nome", "completo", "idade", "nascimento", "renda", "area", "ativo", "meses"]
    assert df["id"].to_list() == g.cpf(N, name="id", unique=True, formatted=True).to_list()
    assert df["sexo"].to_list() == g.sex(N, name="sexo").to_list()
    assert df["nome"].to_list() == g.first_name(N, name="nome", sex=df["sexo"]).to_list()
    assert df["completo"].to_list() == g.full_name(N, name="completo", sex=df["sexo"], null_fraction=0.1).to_list()
    assert df["nascimento"].to_list() == g.birthdate(N, name="nascimento", age=df["idade"], on=ON).to_list()
    assert df["meses"].to_list() == [a * 12 for a in df["idade"].to_list()]


def test_table_same_for_any_threads() -> None:
    a = dg.DataGen(seed=SEED, threads=1).table(N, people_schema())
    b = dg.DataGen(seed=SEED, threads=4).table(N, people_schema())
    for c in a.columns:
        assert a[c].to_list() == b[c].to_list(), c


def test_table_column_independent_of_other_columns() -> None:
    g = dg.DataGen(seed=SEED)
    big = g.table(1000, {"a": "integer", "b": "cpf", "c": "sentence"})
    small = g.table(1000, {"c": "sentence", "a": "integer"})
    assert big["a"].to_list() == small["a"].to_list()
    assert big["c"].to_list() == small["c"].to_list()


def test_table_accepts_every_spec_form() -> None:
    g = dg.DataGen(seed=1)
    df = g.table(10, {
        "a": "integer",
        "b": ("integer", {"low": 5, "high": 6}),
        "c": ("integer", dg.IntegerConfig(low=7, high=7)),
        "d": dg.CPFConfig(formatted=True),
        "e": dg.column("choice", ["x", "y"], weights=[1, 0]),
        "f": pl.col("b") * 2,
    })  # fmt: skip
    assert df.columns == list("abcdef")
    assert set(df["b"].to_list()) <= {5, 6}
    assert set(df["c"].to_list()) == {7}
    assert all(len(x) == 14 for x in df["d"].to_list())
    assert set(df["e"].to_list()) == {"x"}
    assert df["d"].to_list() == g.cpf(10, name="d", formatted=True).to_list()


def test_table_zero_rows_and_schema_reuse() -> None:
    s = people_schema()
    g = dg.DataGen(seed=3)
    assert g.table(0, s).height == 0
    assert g.table(500, s)["nome"].to_list() == g.table(500, s)["nome"].to_list()


def test_module_level_table() -> None:
    a = dg.table(100, {"x": "uuid"}, seed=9)
    b = dg.DataGen(seed=9).table(100, {"x": "uuid"})
    assert a["x"].to_list() == b["x"].to_list()


# ----------------------------------------------------------------------------- erros de schema
@pytest.mark.parametrize(
    ("spec", "msg"),
    [
        ({"a": ("first_name", {"sex": dg.ref("b")})}, "não estão no schema"),
        ({"a": ("first_name", {"sex": dg.ref("a")})}, "dela mesma"),
        ({"a": ("integer", {"low": dg.ref("b")}), "b": "integer"}, "ref só vale"),
        ({"a": ("integer", {"name": "outro"})}, "chave do schema"),
        ({"a": ("first_name", {"sex": ["F", "M"]})}, "dg.ref"),
        ({"a": 123}, "use 'tipo'"),
        ({}, "não tem colunas"),
    ],
)
def test_schema_errors(spec: dict, msg: str) -> None:
    with pytest.raises((ValueError, TypeError), match=msg):
        dg.Schema(spec)


def test_schema_cycle() -> None:
    with pytest.raises(ValueError, match="circular"):
        dg.Schema(
            {
                "a": ("correlated", {"other": dg.ref("b"), "rho": 0.1}),
                "b": ("correlated", {"other": dg.ref("a"), "rho": 0.1}),
            }
        )


def test_unknown_kind_suggests() -> None:
    with pytest.raises(KeyError, match="first_name"):
        dg.Schema({"a": "first_nam"})


def test_correlated_needs_moments_of_expression() -> None:
    s = dg.Schema({"x": "integer", "y": pl.col("x") * 2, "z": ("correlated", {"other": dg.ref("y"), "rho": 0.3})})
    with pytest.raises(ValueError, match="center"):
        dg.DataGen(seed=1).table(10, s)
    ok = dg.Schema({
        "x": "integer", "y": pl.col("x") * 2,
        "z": ("correlated", {"other": dg.ref("y"), "rho": 0.3, "center": 100.0, "scale": 58.0}),
    })  # fmt: skip
    assert dg.DataGen(seed=1).table(10, ok).height == 10


def test_select_keeps_dependencies() -> None:
    s = people_schema().select(["nascimento", "meses"])
    assert s.names == ("idade", "nascimento", "meses")


# ----------------------------------------------------------------------------- lotes (o que scan usa)
def test_batches_equal_whole_table() -> None:
    s = people_schema().bind(dg.DataGen(seed=SEED).locale)
    c = ctx()
    whole = s.run(c, 2 * BLOCK_ROWS + 10)
    parts = list(iter_batches(s, c, 2 * BLOCK_ROWS + 10, BLOCK_ROWS))
    assert [p.height for p in parts] == [BLOCK_ROWS, BLOCK_ROWS, 10]
    for name in s.names:
        assert concat_lists(parts, name) == whole[name].to_list(), name


def test_scan_source_projection_and_limit() -> None:
    s = people_schema().bind(dg.DataGen(seed=SEED).locale)
    c = ctx()
    whole = s.run(c, N)
    got = list(scan_source(s, c, N, ["nascimento"], None, 1000, None))
    assert len(got) == 1
    assert got[0].columns == ["nascimento"]
    assert got[0]["nascimento"].to_list() == whole["nascimento"].to_list()[:1000]


def test_scan_source_predicate_and_limit() -> None:
    s = people_schema().bind(dg.DataGen(seed=SEED).locale)
    c = ctx()
    whole = s.run(c, N)
    want = [n for n, sx in zip(whole["nome"].to_list(), whole["sexo"].to_list(), strict=True) if sx == "F"]
    got = list(scan_source(s, c, N, ["nome"], pl.col("sexo") == "F", None, BLOCK_ROWS))
    assert concat_lists(got, "nome") == want
    limited = list(scan_source(s, c, N, ["nome"], pl.col("sexo") == "F", 50, None))
    assert concat_lists(limited, "nome") == want[:50]


@pytest.mark.skipif(FAKE, reason="precisa do Polars de verdade")
def test_scan_collect_equals_table() -> None:
    g = dg.DataGen(seed=SEED)
    s = people_schema()
    lf = g.scan(N, s, batch_size=BLOCK_ROWS)
    assert isinstance(lf, pl.LazyFrame)
    assert lf.collect().equals(g.table(N, s))
    assert lf.select("id").head(7).collect()["id"].to_list() == g.table(7, s)["id"].to_list()
    adults = lf.filter(pl.col("idade") >= 60).select("nome", "idade").collect()
    t = g.table(N, s).filter(pl.col("idade") >= 60).select("nome", "idade")
    assert adults.equals(t)
    assert lf.select(pl.len()).collect().item() == N


@pytest.mark.skipif(FAKE, reason="precisa do Polars de verdade")
@pytest.mark.parametrize("engine", ["streaming", "in-memory"])
def test_scan_ignores_polars_batch_hint(
    engine: Literal["streaming", "in-memory"], monkeypatch: pytest.MonkeyPatch
) -> None:
    # o motor streaming sugere lotes pequenos; seguir a sugestão tirava o paralelismo entre blocos
    from nini_datagen.schema import lazy  # noqa: PLC0415

    seen: list[Any] = []
    original = lazy.scan_source

    def spy(*a: Any) -> Any:
        seen.append(a[-1])
        return original(*a)

    monkeypatch.setattr(lazy, "scan_source", spy)
    g = dg.DataGen(seed=SEED)
    s = people_schema()
    assert g.scan(N, s).collect(engine=engine).equals(g.table(N, s))
    assert seen
    assert all(b is None for b in seen)
    seen.clear()
    g.scan(N, s, batch_size=BLOCK_ROWS).collect(engine=engine)
    assert seen
    assert all(b == BLOCK_ROWS for b in seen)


@pytest.mark.skipif(FAKE, reason="precisa do Polars de verdade")
def test_scan_schema_matches_table() -> None:
    g = dg.DataGen(seed=SEED)
    assert g.scan(10, people_schema()).collect_schema() == g.table(10, people_schema()).schema


# ----------------------------------------------------------------------------- geradores dependentes
def test_birthdate_coherent_with_age() -> None:
    g = dg.DataGen(seed=5)
    ages = pl.Series("idade", [0, 1, 17, 18, 64, 100, None] * 2000)
    born = g.birthdate(len(ages), age=ages, on=dt.date(2024, 2, 29)).to_list()
    on = dt.date(2024, 2, 29)
    for a, b in zip(ages.to_list(), born, strict=True):
        if a is None:
            assert b is None
            continue
        years = on.year - b.year - ((on.month, on.day) < (b.month, b.day))
        assert years == a, (a, b)


def test_birthdate_needs_age_and_rejects_negative() -> None:
    g = dg.DataGen(seed=5)
    with pytest.raises(ValueError, match="age"):
        g.birthdate(3, on=dt.date(2026, 1, 1))
    with pytest.raises(ValueError, match="negativ"):
        g.birthdate(2, age=[1, -1], on=dt.date(2026, 1, 1))


def test_birthdate_requires_on() -> None:
    g = dg.DataGen(seed=5)
    with pytest.raises(ValueError, match="precisa de `on`"):
        g.birthdate(3, age=[30, 31, 32])
    with pytest.raises(ValueError, match="precisa de `on`"):
        dg.BirthdateConfig.model_validate({})
    with pytest.raises(ValueError, match="precisa de `on`"):
        g.table(3, {"idade": "age", "nasc": ("birthdate", {"age": dg.ref("idade")})})
    assert dg.BirthdateConfig.model_validate({"on": "2026-01-01"}).on == dt.date(2026, 1, 1)


def test_correlated_statistics() -> None:
    g = dg.DataGen(seed=11)
    x = g.normal(200_000, mean=40, std=10)
    y = np.asarray(g.correlated(200_000, other=x, rho=-0.7, mean=2.0, std=3.0).to_list())
    xs = np.asarray(x.to_list())
    assert abs(np.corrcoef(xs, y)[0, 1] + 0.7) < 0.01
    assert abs(y.mean() - 2.0) < 0.03
    assert abs(y.std() - 3.0) < 0.03


def test_correlated_in_table_uses_known_moments() -> None:
    s = dg.Schema({"x": ("uniform", {"low": 0, "high": 12}), "y": ("correlated", {"other": dg.ref("x"), "rho": 1.0})})
    df = dg.DataGen(seed=2).table(1000, s)
    x, y = np.asarray(df["x"].to_list()), np.asarray(df["y"].to_list())
    assert np.allclose(y, (x - 6.0) / np.sqrt(12.0))


def test_choice_by_distribution_default_and_nulls() -> None:
    g = dg.DataGen(seed=13)
    by = pl.Series("by", ["F", "M", "X", None] * 25_000)
    out = g.choice_by(len(by), by=by, options={"F": ["a"], "M": (["b", "c"], [1, 3])}).to_list()
    pairs = Counter(zip(by.to_list(), out, strict=True))
    assert pairs[("F", "a")] == 25_000
    assert pairs[("X", None)] == pairs[(None, None)] == 25_000
    assert abs(pairs[("M", "c")] / 25_000 - 0.75) < 0.02
    with_default = g.choice_by(len(by), by=by, options={"F": ["a"]}, default=["z"]).to_list()
    assert set(with_default) == {"a", "z"}


def test_choice_by_config_errors() -> None:
    with pytest.raises(ValueError, match="não vazio"):
        dg.ChoiceByConfig.model_validate({"options": {}})
    with pytest.raises(ValueError, match="pesos"):
        dg.ChoiceByConfig.model_validate({"options": {"a": (["x", "y"], [1])}})
