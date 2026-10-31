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


def _single(name: str) -> Callable[[], pl.DataFrame]:
    def build() -> pl.DataFrame:
        kind, kw = case(name)
        g = dg.DataGen(seed=SEED)
        return pl.DataFrame([g.generate(kind, N, **kw), g.generate(kind, N, name="com_nulos", null_fraction=0.1, **kw)])

    return build


def _people() -> pl.DataFrame:
    g = dg.DataGen(seed=SEED)
    sx = g.sex(N)
    return pl.DataFrame([sx, g.first_name(N, sex=sx), g.full_name(N, sex=sx), g.age(N)])


GOLDEN_CASES: dict[str, Callable[[], pl.DataFrame]] = {name: _single(name) for name in sorted(CASES)}
GOLDEN_CASES["people"] = _people


def build(name: str) -> pl.DataFrame:
    df = GOLDEN_CASES[name]()
    return df.with_row_index("_linha")
