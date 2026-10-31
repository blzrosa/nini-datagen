"""Utilitários dos testes dos geradores."""

from __future__ import annotations

from typing import Any

import polars as pl

from nini_datagen.core.blocks import BLOCK_ROWS

# mais de um bloco, e o último incompleto (testa a divisão e a costura dos blocos)
N_MULTI = 2 * BLOCK_ROWS + 1_234

# uma configuração "típica" de cada tipo, usada nos testes genéricos (determinismo, nulos, n=0...)
CASES: dict[str, dict[str, Any]] = {
    "integer": {"low": -5, "high": 1000},
    "integer64": {"kind": "integer", "low": -(2**40), "high": 2**40},
    "uniform": {"low": -1.0, "high": 3.0},
    "uniform32": {"kind": "uniform", "dtype": "float32"},
    "normal": {"mean": 10.0, "std": 2.0},
    "lognormal": {"mean": 1.0, "sigma": 0.5},
    "boolean": {"p": 0.3},
    "date": {"start": "2020-01-01", "end": "2020-12-31"},
    "datetime": {"start": "2020-01-01", "end": "2021-01-01", "unit": "ms"},
    "choice": {"values": ["ana", "bia", "uma opção bem longa"], "weights": [3, 2, 1]},
    "choice_uniform": {"kind": "choice", "values": ["x", "y", "z", "w"]},
    "choice_int": {"kind": "choice", "values": [10, 20, 30]},
    "choice_bool": {"kind": "choice", "values": [True, False], "weights": [9, 1]},
    "sex": {},
    "age": {"low": 18, "high": 90},
    "first_name": {},
    "first_name_f": {"kind": "first_name", "sex": "F"},
    "last_name": {},
    "full_name": {},
}

DTYPES = {
    "integer": pl.Int32,
    "integer64": pl.Int64,
    "uniform": pl.Float64,
    "uniform32": pl.Float32,
    "normal": pl.Float64,
    "lognormal": pl.Float64,
    "boolean": pl.Boolean,
    "date": pl.Date,
    "datetime": pl.Datetime("ms"),
    "choice": pl.String,
    "choice_uniform": pl.String,
    "choice_int": pl.Int64,
    "choice_bool": pl.Boolean,
    "sex": pl.String,
    "age": pl.Int32,
    "first_name": pl.String,
    "first_name_f": pl.String,
    "last_name": pl.String,
    "full_name": pl.String,
}


def case(name: str) -> tuple[str, dict[str, Any]]:
    kw = dict(CASES[name])
    return kw.pop("kind", name), kw


def same(a: pl.Series, b: pl.Series) -> bool:
    """Igualdade exata (valores, nulos, tipo e nome)."""
    return a.dtype == b.dtype and a.name == b.name and a.to_list() == b.to_list()
