"""Inteiros, reais, normal, lognormal, booleanos, datas e instantes."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from .._native import lib
from ..config.numbers import (
    BooleanConfig,
    DateConfig,
    DatetimeConfig,
    IntegerConfig,
    LognormalConfig,
    NormalConfig,
    UniformConfig,
    epoch,
)
from ..core.arrow import arrow_type
from ..locales import Locale
from ..registry import registry
from .base import ArrayJob, BitsJob, Job, Provider, Run, probability_threshold

_EPOCH_ORDINAL = 719_163  # date(1970, 1, 1).toordinal()


@registry.register
class IntegerProvider(Provider[IntegerConfig]):
    kind = "integer"
    config_cls = IntegerConfig
    ns_per_row = 1.2

    def plan(self, run: Run, config: IntegerConfig, inputs: Mapping[str, Any]) -> Job:
        low, span = config.low, config.high - config.low + 1
        if config.resolved_dtype == "int32" and span < 2**32:
            f32 = lib().dg_rand_i32
            return ArrayJob(run.n, np.int32, lambda st, m, o: f32(st, low, span, m, o))
        f64 = lib().dg_rand_i64
        return ArrayJob(run.n, np.int64, lambda st, m, o: f64(st, low, span, m, o))

    def moments(self, config: IntegerConfig, locale: Locale) -> tuple[float, float]:
        span = config.high - config.low + 1
        return (config.low + config.high) / 2, math.sqrt((span * span - 1) / 12)


@registry.register
class UniformProvider(Provider[UniformConfig]):
    kind = "uniform"
    config_cls = UniformConfig
    ns_per_row = 1.3

    def plan(self, run: Run, config: UniformConfig, inputs: Mapping[str, Any]) -> Job:
        lo, hi = config.low, config.high
        if config.dtype == "float32":
            f32 = lib().dg_rand_f32
            return ArrayJob(run.n, np.float32, lambda st, m, o: f32(st, lo, hi, m, o))
        f64 = lib().dg_rand_f64
        return ArrayJob(run.n, np.float64, lambda st, m, o: f64(st, lo, hi, m, o))

    def moments(self, config: UniformConfig, locale: Locale) -> tuple[float, float]:
        return (config.low + config.high) / 2, (config.high - config.low) / math.sqrt(12)


@registry.register
class NormalProvider(Provider[NormalConfig]):
    kind = "normal"
    config_cls = NormalConfig
    ns_per_row = 3.5

    def plan(self, run: Run, config: NormalConfig, inputs: Mapping[str, Any]) -> Job:
        fn, mu, sd = lib().dg_rand_normal, config.mean, config.std
        return ArrayJob(run.n, np.float64, lambda st, m, o: fn(st, mu, sd, 0, m, o))

    def moments(self, config: NormalConfig, locale: Locale) -> tuple[float, float]:
        return config.mean, config.std


@registry.register
class LognormalProvider(Provider[LognormalConfig]):
    kind = "lognormal"
    config_cls = LognormalConfig
    ns_per_row = 4.3

    def plan(self, run: Run, config: LognormalConfig, inputs: Mapping[str, Any]) -> Job:
        fn, mu, sd = lib().dg_rand_normal, config.mean, config.sigma
        return ArrayJob(run.n, np.float64, lambda st, m, o: fn(st, mu, sd, 1, m, o))

    def moments(self, config: LognormalConfig, locale: Locale) -> tuple[float, float]:
        exp = lib().dg_det_exp  # o exp determinístico do C++ (o math.exp depende da biblioteca do sistema)
        mu, s2 = config.mean, config.sigma * config.sigma
        return exp(mu + s2 / 2), math.sqrt((exp(s2) - 1.0) * exp(2 * mu + s2))


@registry.register
class BooleanProvider(Provider[BooleanConfig]):
    kind = "boolean"
    config_cls = BooleanConfig
    ns_per_row = 0.2  # 64 linhas por palavra: nunca vale paralelizar

    def plan(self, run: Run, config: BooleanConfig, inputs: Mapping[str, Any]) -> Job:
        return BitsJob(run.n, probability_threshold(config.p))


@registry.register
class DateProvider(Provider[DateConfig]):
    kind = "date"
    config_cls = DateConfig
    ns_per_row = 1.2

    def plan(self, run: Run, config: DateConfig, inputs: Mapping[str, Any]) -> Job:
        a = config.start.toordinal() - _EPOCH_ORDINAL
        span = config.end.toordinal() - config.start.toordinal() + 1
        fn = lib().dg_rand_i32
        return ArrayJob(run.n, np.int32, lambda st, m, o: fn(st, a, span, m, o), typ=arrow_type("date"))


@registry.register
class DatetimeProvider(Provider[DatetimeConfig]):
    kind = "datetime"
    config_cls = DatetimeConfig
    ns_per_row = 1.2

    def plan(self, run: Run, config: DatetimeConfig, inputs: Mapping[str, Any]) -> Job:
        a, b = epoch(config.start, config.unit), epoch(config.end, config.unit)
        span = b - a
        if span >= 2**64:
            raise ValueError("intervalo grande demais para a unidade escolhida")
        fn = lib().dg_rand_i64
        typ = arrow_type("datetime", config.unit)
        return ArrayJob(run.n, np.int64, lambda st, m, o: fn(st, a, span, m, o), typ=typ)
