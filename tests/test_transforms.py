"""Dados sujos (`dirty`), duplicatas (`add_duplicates`) e gravação em lotes (`write_parquet_dataset`)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

import nini_datagen as dg
from nini_datagen.core.blocks import BLOCK_ROWS
from nini_datagen.registry import registry

pl = pytest.importorskip("polars")
FAKE = getattr(pl, "IS_FAKE", False)
N = BLOCK_ROWS + 300
ALL_TEXT = {"typo": 0.1, "unmask": 0.2, "case": 0.05, "whitespace": 0.05, "null_like": 0.05, "truncate": 0.05}


# ----------------------------------------------------------------------------- dirty
def test_dirty_is_deterministic_and_batch_stable() -> None:
    g = dg.DataGen(seed=4)
    cfg = registry.config("cpf", None, formatted=True, dirty=ALL_TEXT)
    provider = registry.get("cpf")
    full = provider.generate(N, cfg, g._ctx).to_list()
    parts = provider.generate(BLOCK_ROWS, cfg, g._ctx, None, 0).to_list()
    parts += provider.generate(N - BLOCK_ROWS, cfg, g._ctx, None, 1).to_list()
    assert parts == full
    assert full == g.cpf(N, formatted=True, dirty=ALL_TEXT).to_list()


def test_dirty_fractions_and_effects() -> None:
    g = dg.DataGen(seed=5)
    clean = g.cpf(20_000, formatted=True).to_list()
    dirty = g.cpf(20_000, formatted=True, dirty={"unmask": 0.3}).to_list()
    changed = [(a, b) for a, b in zip(clean, dirty, strict=True) if a != b]
    assert 0.27 < len(changed) / 20_000 < 0.33
    assert all(b == a.replace(".", "").replace("-", "") for a, b in changed)


def test_dirty_null_like_and_whitespace() -> None:
    g = dg.DataGen(seed=6)
    out = g.first_name(10_000, dirty={"null_like": 0.1, "null_tokens": ["N/A", "-"]}).to_list()
    c = Counter(x for x in out if x in ("N/A", "-"))
    assert 0.08 < sum(c.values()) / 10_000 < 0.12
    ws = g.first_name(10_000, name="w", dirty={"whitespace": 1.0}).to_list()
    assert all(x != x.strip() for x in ws)


def test_dirty_typo_changes_one_position() -> None:
    g = dg.DataGen(seed=7)
    clean = g.last_name(5_000, name="s").to_list()
    typo = g.last_name(5_000, name="s", dirty={"typo": 1.0}).to_list()
    for a, b in zip(clean, typo, strict=True):
        assert abs(len(a) - len(b)) <= 1


def test_dirty_numbers_outliers_and_sentinel() -> None:
    g = dg.DataGen(seed=8)
    x = g.integer(10_000, low=1, high=9, dirty={"outliers": 0.1, "sentinel": [(-1, 0.05)]}).to_list()
    assert 0.03 < x.count(-1) / 10_000 < 0.07
    assert any(v >= 10 for v in x)


def test_dirty_type_errors() -> None:
    g = dg.DataGen(seed=1)
    with pytest.raises(ValueError, match="só valem para texto"):
        g.integer(10, dirty={"typo": 0.5})
    with pytest.raises(ValueError, match="números"):
        g.first_name(10, dirty={"outliers": 0.5})
    with pytest.raises(ValidationError):
        dg.DirtyConfig.model_validate({"typo": 2})
    with pytest.raises(ValidationError):
        dg.DirtyConfig.model_validate({"tipo": 0.1})


def test_dirty_standalone_and_mojibake() -> None:
    s = pl.Series("cidade", ["São Paulo", "Ribeirão Preto", None])
    out = dg.dirty(s, mojibake=1.0, seed=1).to_list()
    assert out == ["SÃ£o Paulo", "RibeirÃ£o Preto", None]
    assert dg.dirty(s, accents=1.0, seed=1).to_list() == ["Sao Paulo", "Ribeirao Preto", None]
    assert dg.dirty(s, typo=0.5, seed=3).to_list() == dg.dirty(s, typo=0.5, seed=3).to_list()


def test_dirty_in_table_matches_standalone() -> None:
    g = dg.DataGen(seed=9)
    df = g.table(5_000, {"doc": ("cpf", {"formatted": True, "dirty": {"unmask": 0.5}}), "n": "integer"})
    assert df["doc"].to_list() == g.cpf(5_000, name="doc", formatted=True, dirty={"unmask": 0.5}).to_list()


# ----------------------------------------------------------------------------- duplicatas
def test_add_duplicates_exact_copies() -> None:
    g = dg.DataGen(seed=10)
    df = g.table(1_000, {"nome": "full_name", "cpf": "cpf"})
    out = g.add_duplicates(df, 0.1)
    assert out.height == 1_100
    by_id = {
        r: (n, c) for r, n, c in zip(out["row_id"].to_list(), out["nome"].to_list(), out["cpf"].to_list(), strict=True)
    }
    dups = [(r, d) for r, d in zip(out["row_id"].to_list(), out["dup_of"].to_list(), strict=True) if d is not None]
    assert len(dups) == 100
    assert all(r >= 1_000 and by_id[r] == by_id[d] for r, d in dups)
    assert out["row_id"].to_list() == g.add_duplicates(df, 0.1)["row_id"].to_list()


def test_add_duplicates_dirty_and_no_shuffle() -> None:
    g = dg.DataGen(seed=11)
    df = g.table(500, {"nome": "full_name"})
    out = g.add_duplicates(df, 0.2, dirty={"nome": {"case": 1.0}}, shuffle=False)
    assert out["row_id"].to_list() == list(range(600))
    names = out["nome"].to_list()
    src = out["dup_of"].to_list()[500:]
    assert all(names[500 + i] in (names[s].upper(), names[s].lower()) for i, s in enumerate(src))


def test_add_duplicates_errors() -> None:
    df = dg.table(10, {"a": "integer"}, seed=1)
    with pytest.raises(ValueError, match="não existem"):
        dg.add_duplicates(df, 0.5, dirty={"b": {"typo": 0.1}})
    with pytest.raises(ValueError, match="já existe"):
        dg.add_duplicates(df.with_columns(pl.Series("row_id", list(range(10)))), 0.5)
    assert dg.add_duplicates(df, 0.0)["dup_of"].null_count() == 10


# ----------------------------------------------------------------------------- write_parquet_dataset
SCHEMA = {"uf": "state", "id": ("cpf", {"unique": True}), "x": ("integer", {"null_fraction": 0.1})}


def test_write_dataset_file_layout(tmp_path: Path) -> None:
    g = dg.DataGen(seed=12)
    files = g.write_parquet_dataset(tmp_path / "a", 3 * BLOCK_ROWS, SCHEMA, batch_rows=BLOCK_ROWS)
    assert [f.name for f in files] == ["part-00000.parquet", "part-00001.parquet", "part-00002.parquet"]
    parts = g.write_parquet_dataset(tmp_path / "b", 20_000, SCHEMA, partition_by="uf", rows_per_file=1_000)
    assert all(f.parent.name.startswith("uf=") for f in parts)
    assert len({f.parent.name for f in parts}) == 27


def test_write_dataset_errors(tmp_path: Path) -> None:
    g = dg.DataGen(seed=1)
    with pytest.raises(ValueError, match="partition_by"):
        g.write_parquet_dataset(tmp_path, 10, SCHEMA, partition_by="nada")
    with pytest.raises(ValueError, match="compression"):
        g.write_parquet_dataset(tmp_path, 10, SCHEMA, compression="rar")
    with pytest.raises(ValueError, match="partições distintas"):
        g.write_parquet_dataset(tmp_path, 1_000, SCHEMA, partition_by="id", max_partitions=10)


@pytest.mark.skipif(FAKE, reason="precisa do Polars de verdade (Parquet)")
@pytest.mark.parametrize("batch", [BLOCK_ROWS, 2 * BLOCK_ROWS, None])
def test_write_dataset_equals_table(tmp_path: Path, batch: int | None) -> None:
    g = dg.DataGen(seed=13)
    n = 3 * BLOCK_ROWS + 77
    g.write_parquet_dataset(tmp_path, n, SCHEMA, batch_rows=batch)
    back = pl.read_parquet(tmp_path / "*.parquet")
    assert back.equals(g.table(n, SCHEMA))


@pytest.mark.skipif(FAKE, reason="precisa do Polars de verdade (Parquet)")
def test_write_dataset_partitions_roundtrip(tmp_path: Path) -> None:
    g = dg.DataGen(seed=14)
    n = BLOCK_ROWS + 10
    files = g.write_parquet_dataset(tmp_path, n, SCHEMA, partition_by="uf", rows_per_file=3_000)
    back = pl.scan_parquet(tmp_path, hive_partitioning=True).collect()
    want = g.table(n, SCHEMA)
    assert back.height == n
    assert sorted(back["id"].to_list()) == sorted(want["id"].to_list())
    by_dir = Counter(f.parent.name for f in files)
    assert all(pl.read_parquet(f).height <= 3_000 for f in files)
    assert sum(by_dir.values()) == len(files)
