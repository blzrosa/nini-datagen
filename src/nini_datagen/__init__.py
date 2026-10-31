"""nini-datagen: dados sintéticos realistas do Brasil em escala, gerados por kernels C++ direto em Polars.

>>> import nini_datagen as dg
>>> dg.first_name(5, seed=42)                     # doctest: +SKIP
>>> g = dg.DataGen(seed=42)
>>> g.integer(1_000_000, low=1, high=6)           # doctest: +SKIP
>>> g.choice(10, ["a", "b", "c"], weights=[5, 3, 2])  # doctest: +SKIP

Toda configuração é um modelo Pydantic (``dg.IntegerConfig(low=1, high=6)``); dicts e kwargs são convertidos para ele,
então um parâmetro com nome errado vira erro em vez de ser ignorado.
"""

from __future__ import annotations

from importlib import metadata

from .api import (
    age,
    boolean,
    choice,
    date,
    datetime,
    first_name,
    full_name,
    generate,
    integer,
    last_name,
    lognormal,
    normal,
    sex,
    uniform,
)
from .config import (
    AgeConfig,
    BaseConfig,
    BooleanConfig,
    ChoiceConfig,
    DateConfig,
    DatetimeConfig,
    FirstNameConfig,
    FullNameConfig,
    IntegerConfig,
    LastNameConfig,
    LognormalConfig,
    NormalConfig,
    SexConfig,
    UniformConfig,
)
from .errors import DatagenError, NativeLibraryError
from .generator import DataGen
from .registry import registry

try:
    __version__ = metadata.version("nini-datagen")
except metadata.PackageNotFoundError:  # rodando de uma cópia sem instalar
    __version__ = "0.0.0"

__all__ = [
    "AgeConfig",
    "BaseConfig",
    "BooleanConfig",
    "ChoiceConfig",
    "DataGen",
    "DatagenError",
    "DateConfig",
    "DatetimeConfig",
    "FirstNameConfig",
    "FullNameConfig",
    "IntegerConfig",
    "LastNameConfig",
    "LognormalConfig",
    "NativeLibraryError",
    "NormalConfig",
    "SexConfig",
    "UniformConfig",
    "__version__",
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
    "registry",
    "sex",
    "uniform",
]
