"""Funções soltas: ``nini_datagen.integer(n, ...)`` é um atalho para ``DataGen(seed, ...).integer(n, ...)``.

Sem ``seed``, cada chamada sorteia uma semente nova (valores diferentes a cada vez). Com ``seed``, o resultado é sempre
o mesmo.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from .generator import DataGen
from .locales import Locale

__all__ = [
    "age",
    "boolean",
    "choice",
    "date",
    "datetime",
    "first_name",
    "full_name",
    "generate",
    "integer",
    "last_name",
    "lognormal",
    "normal",
    "sex",
    "uniform",
]


def generate(
    kind: str,
    n: int,
    config: Any = None,
    /,
    *,
    seed: int | None = None,
    locale: str | Locale = "pt_BR",
    threads: int | None = None,
    **kwargs: Any,
) -> pl.Series:
    """Gera ``n`` valores do tipo ``kind``; veja `DataGen.generate`."""
    return DataGen(seed, locale=locale, threads=threads).generate(kind, n, config, **kwargs)


def _shortcut(kind: str, doc: str) -> Any:
    def fn(
        n: int,
        config: Any = None,
        /,
        *,
        seed: int | None = None,
        locale: str | Locale = "pt_BR",
        threads: int | None = None,
        **kwargs: Any,
    ) -> pl.Series:
        return generate(kind, n, config, seed=seed, locale=locale, threads=threads, **kwargs)

    fn.__name__ = fn.__qualname__ = kind
    fn.__doc__ = doc + "\n\n``seed``, ``locale`` e ``threads`` como em `DataGen`; o resto vai para a configuração."
    return fn


integer = _shortcut("integer", DataGen.integer.__doc__ or "")
uniform = _shortcut("uniform", DataGen.uniform.__doc__ or "")
normal = _shortcut("normal", DataGen.normal.__doc__ or "")
lognormal = _shortcut("lognormal", DataGen.lognormal.__doc__ or "")
boolean = _shortcut("boolean", DataGen.boolean.__doc__ or "")
date = _shortcut("date", DataGen.date.__doc__ or "")
datetime = _shortcut("datetime", DataGen.datetime.__doc__ or "")
choice = _shortcut("choice", DataGen.choice.__doc__ or "")
sex = _shortcut("sex", DataGen.sex.__doc__ or "")
age = _shortcut("age", DataGen.age.__doc__ or "")
first_name = _shortcut("first_name", DataGen.first_name.__doc__ or "")
last_name = _shortcut("last_name", DataGen.last_name.__doc__ or "")
full_name = _shortcut("full_name", DataGen.full_name.__doc__ or "")
