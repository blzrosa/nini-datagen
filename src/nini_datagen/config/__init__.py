"""Configurações dos geradores (modelos Pydantic imutáveis; parâmetro com nome errado vira erro)."""

from __future__ import annotations

from .base import BaseConfig
from .choice import ChoiceConfig
from .numbers import (
    BooleanConfig,
    DateConfig,
    DatetimeConfig,
    IntegerConfig,
    LognormalConfig,
    NormalConfig,
    UniformConfig,
)
from .person import AgeConfig, FirstNameConfig, FullNameConfig, LastNameConfig, SexConfig

__all__ = [
    "AgeConfig",
    "BaseConfig",
    "BooleanConfig",
    "ChoiceConfig",
    "DateConfig",
    "DatetimeConfig",
    "FirstNameConfig",
    "FullNameConfig",
    "IntegerConfig",
    "LastNameConfig",
    "LognormalConfig",
    "NormalConfig",
    "SexConfig",
    "UniformConfig",
]
