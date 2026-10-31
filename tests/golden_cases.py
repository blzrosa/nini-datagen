"""Casos dos gabaritos da v0.2.0: cada um vira ``tests/golden/<nome>.parquet`` (100 mil linhas, semente fixa).

Um gabarito só é gravado quando o gerador está no formato final; depois disso, toda versão tem que reproduzi-lo
exatamente. Mudar um gabarito de propósito exige registrar o motivo no CHANGELOG (quebra a reprodutibilidade de quem
usa a semente).
"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl

import nini_datagen as dg

from .helpers import CASES, case

SEED = 20_261_030
N = 100_000
LITE_KINDS = {"cep", "address"}


def _single(name: str) -> Callable[[], pl.DataFrame]:
    def build() -> pl.DataFrame:
        kind, kw = case(name)
        if kind in LITE_KINDS:
            # fixa a base embutida: o gabarito sai igual com ou sem a base completa no cache (CI não a tem)
            kw = {"source": "lite", **kw}
        g = dg.DataGen(seed=SEED)
        return pl.DataFrame([g.generate(kind, N, **kw), g.generate(kind, N, name="com_nulos", null_fraction=0.1, **kw)])

    return build


def _people() -> pl.DataFrame:
    g = dg.DataGen(seed=SEED)
    sx = g.sex(N)
    return pl.DataFrame([sx, g.first_name(N, sex=sx), g.full_name(N, sex=sx), g.age(N)])


def _table() -> pl.DataFrame:
    """Geradores que dependem de outra coluna (só existem com ``ref``) e a montagem da tabela."""
    schema = dg.Schema({
        "sexo": "sex",
        "nome": ("first_name", {"sex": dg.ref("sexo")}),
        "completo": ("full_name", {"sex": dg.ref("sexo"), "null_fraction": 0.1}),
        "idade": ("age", {"low": 18, "high": 90, "null_fraction": 0.05}),
        "nascimento": ("birthdate", {"age": dg.ref("idade"), "on": "2026-01-01"}),
        "renda": ("correlated", {"other": dg.ref("idade"), "rho": 0.5, "mean": 8, "std": 0.6, "lognormal": True}),
        "area": ("choice_by", {"by": dg.ref("sexo"), "options": {"F": ["a", "b"], "M": (["c", "d"], [1, 3])}}),
        "meses": pl.col("idade") * 12,
    })  # fmt: skip
    return dg.DataGen(seed=SEED).table(N, schema)


def _dirty() -> pl.DataFrame:
    """Todos os defeitos de `DirtyConfig` e as duplicatas (cópias sujas, embaralhadas)."""
    text = {"accents": 0.05, "mojibake": 0.02, "unmask": 0.3, "typo": 0.05, "truncate": 0.02, "case": 0.03,
            "whitespace": 0.03, "null_like": 0.02}  # fmt: skip
    schema = dg.Schema({
        "cpf": ("cpf", {"formatted": True, "dirty": text}),
        "nome": ("full_name", {"null_fraction": 0.05, "dirty": {**text, "unmask": 0.0}}),
        "valor": ("lognormal", {"mean": 5, "sigma": 1, "dirty": {"outliers": 0.01, "sentinel": [(-1.0, 0.02)]}}),
        "qtd": ("integer", {"low": 1, "high": 99, "dirty": {"outliers": 0.01, "sentinel": [(0, 0.01), (9999, 0.01)]}}),
    })  # fmt: skip
    g = dg.DataGen(seed=SEED)
    return g.add_duplicates(g.table(N, schema), 0.05, dirty={"nome": {"typo": 0.5}, "cpf": {"unmask": 0.5}})


# gabaritos ainda não gravados (esperando a conferência das amostras): sem o arquivo o teste é pulado, e o
# --record-golden também não grava estes. Depois de conferir, tire da lista e grave.
PENDING: set[str] = set()

GOLDEN_CASES: dict[str, Callable[[], pl.DataFrame]] = {name: _single(name) for name in sorted(CASES)}
GOLDEN_CASES["people"] = _people
GOLDEN_CASES["table"] = _table
GOLDEN_CASES["dirty"] = _dirty


def build(name: str) -> pl.DataFrame:
    df = GOLDEN_CASES[name]()
    return df.with_row_index("_linha")
