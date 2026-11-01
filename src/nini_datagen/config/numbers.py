"""Configurações dos geradores numéricos e de datas."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import Field, model_validator

from .base import BaseConfig, Probability

__all__ = [
    "BooleanConfig",
    "DateConfig",
    "DatetimeConfig",
    "IntegerConfig",
    "LognormalConfig",
    "NormalConfig",
    "UniformConfig",
]

INT64_MIN, INT64_MAX = -(2**63), 2**63 - 1
INT32_MIN, INT32_MAX = -(2**31), 2**31 - 1


class IntegerConfig(BaseConfig):
    """Inteiros uniformes em ``[low, high]`` (os dois inclusos).

    ``dtype``: ``"int32"`` ou ``"int64"``; o padrão é int32 quando o intervalo cabe nele.
    """

    low: int = Field(default=0, ge=INT64_MIN, le=INT64_MAX)
    high: int = Field(default=100, ge=INT64_MIN, le=INT64_MAX)
    dtype: Literal["int32", "int64"] | None = None

    @model_validator(mode="after")
    def _check(self) -> IntegerConfig:
        if self.high < self.low:
            raise ValueError(f"high ({self.high}) deve ser >= low ({self.low})")
        if self.high - self.low + 1 > 2**64 - 1:
            raise ValueError("intervalo grande demais (máximo 2^64 - 1 valores)")
        if self.dtype == "int32" and not (self.low >= INT32_MIN and self.high <= INT32_MAX):
            raise ValueError("o intervalo não cabe em int32; use dtype='int64'")
        return self

    @property
    def resolved_dtype(self) -> Literal["int32", "int64"]:
        if self.dtype is not None:
            return self.dtype
        return "int32" if self.low >= INT32_MIN and self.high <= INT32_MAX else "int64"


class UniformConfig(BaseConfig):
    """Reais uniformes em ``[low, high)``."""

    low: float = Field(default=0.0, allow_inf_nan=False)
    high: float = Field(default=1.0, allow_inf_nan=False)
    dtype: Literal["float32", "float64"] = "float64"

    @model_validator(mode="after")
    def _check(self) -> UniformConfig:
        if not self.high > self.low:
            raise ValueError(f"high ({self.high}) deve ser > low ({self.low})")
        return self


class NormalConfig(BaseConfig):
    """Normal(``mean``, ``std``), Float64."""

    mean: float = Field(default=0.0, allow_inf_nan=False)
    std: float = Field(default=1.0, gt=0.0, allow_inf_nan=False)


class LognormalConfig(BaseConfig):
    """``exp(Normal(mean, sigma))``, Float64: valores monetários, tamanhos, tempos (cauda longa à direita)."""

    mean: float = Field(default=0.0, allow_inf_nan=False)
    sigma: float = Field(default=1.0, gt=0.0, allow_inf_nan=False)


class BooleanConfig(BaseConfig):
    """Booleanos independentes com P(True) = ``p``."""

    p: float = Probability(0.5, "probabilidade de True")


class DateConfig(BaseConfig):
    """Datas uniformes em ``[start, end]`` (os dois inclusos); aceita ``datetime.date`` ou ``"AAAA-MM-DD"``."""

    start: dt.date = dt.date(2000, 1, 1)
    end: dt.date = dt.date(2025, 12, 31)

    @model_validator(mode="after")
    def _check(self) -> DateConfig:
        if self.end < self.start:
            raise ValueError(f"end ({self.end}) deve ser >= start ({self.start})")
        return self


class DatetimeConfig(BaseConfig):
    """Instantes uniformes em ``[start, end)``, sem fuso horário (``Datetime(unit)`` do Polars).

    ``start``/``end`` aceitam ``datetime`` ou texto ISO (``"2024-01-01"``, ``"2024-01-01T12:00"``). Instantes com fuso
    são convertidos para UTC.
    """

    start: dt.datetime = dt.datetime(2000, 1, 1)
    end: dt.datetime = dt.datetime(2026, 1, 1)
    unit: Literal["ms", "us", "ns"] = "us"

    @model_validator(mode="after")
    def _check(self) -> DatetimeConfig:
        a, b = epoch(self.start, self.unit), epoch(self.end, self.unit)
        if not (a >= INT64_MIN and b <= INT64_MAX):
            raise ValueError(f"intervalo fora do que cabe em Datetime({self.unit!r}) (em 'ns': de 1677 a 2262)")
        if b <= a:
            raise ValueError(f"end ({self.end}) deve ser > start ({self.start})")
        return self


_EPOCH = dt.datetime(1970, 1, 1)
_PER_US = {"ms": None, "us": 1, "ns": 1000}


def epoch(t: dt.datetime, unit: str) -> int:
    """Instante -> inteiro na unidade (desde 1970-01-01 UTC), em aritmética exata (sem float)."""
    if t.tzinfo is not None:
        t = t.astimezone(dt.timezone.utc).replace(tzinfo=None)
    d = t - _EPOCH
    us = (d.days * 86_400 + d.seconds) * 1_000_000 + d.microseconds
    if unit == "ms":
        return us // 1000
    return us * _PER_US[unit]  # type: ignore[operator]
