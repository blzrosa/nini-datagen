"""Geradores que dependem de outra coluna (que chega como dado, ou por ``ref`` numa tabela).

* ``birthdate``: data de nascimento coerente com a idade;
* ``correlated``: real com correlação ``rho`` com uma coluna numérica;
* ``choice_by``: escolha numa lista que depende do valor de outra coluna.

Todos consomem o gerador linha a linha, bloco a bloco (um sorteio por linha), então a coluna é estável por prefixo e
sai igual gerada inteira ou em lotes, como os outros geradores.
"""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Mapping
from typing import Any

import numpy as np
import polars as pl

from .._native import lib, ptr
from ..config.relations import BirthdateConfig, ChoiceByConfig, CorrelatedConfig
from ..core.arrow import arrow_type, primitive_to_series, views_to_series
from ..core.blocks import Block
from ..core.tables import Vocabulary
from ..registry import registry
from .base import Job, Provider, Run

__all__ = [
    "BirthdateProvider",
    "ChoiceByProvider",
    "CorrelatedProvider",
    "as_series",
    "days_before_years",
    "sample_moments",
]

_EPOCH = dt.date(1970, 1, 1)


def as_series(x: Any, what: str, n: int) -> pl.Series:
    """Coluna de entrada (Series, lista, array numpy) -> ``pl.Series`` com ``n`` valores."""
    s = x if isinstance(x, pl.Series) else pl.Series(what, list(x) if not hasattr(x, "tolist") else x.tolist())
    if len(s) != n:
        raise ValueError(f"a coluna {what!r} tem {len(s)} valores, mas n = {n}")
    return s


def _require(inputs: Mapping[str, Any], key: str, kind: str) -> Any:
    if key not in inputs:
        raise ValueError(f"{kind} precisa da coluna {key!r}: {kind}(n, {key}=serie) ou {{{key!r}: dg.ref('coluna')}}")
    return inputs[key]


def _validity_of(s: pl.Series) -> np.ndarray | None:
    """Bits de presença (formato Arrow) de uma coluna com nulos; None se não tem nulos."""
    if s.null_count() == 0:
        return None
    mask = s.is_not_null().to_numpy().astype(np.bool_)
    out = np.zeros(-(-len(s) // 64) * 8, np.uint8)
    packed = np.packbits(mask, bitorder="little")
    out[: len(packed)] = packed
    return out.view(np.uint64)


def _and(a: np.ndarray | None, b: np.ndarray | None) -> np.ndarray | None:
    if a is None:
        return b
    if b is None:
        return a
    return a & b


def sample_moments(x: pl.Series) -> tuple[float, float]:
    """Média e desvio padrão (populacional) dos valores não nulos, com soma exata (`math.fsum`): o resultado não
    depende da ordem da soma, então é o mesmo em qualquer máquina (a soma do Polars e do numpy pode mudar o último
    bit conforme a CPU)."""
    v = x.drop_nulls().to_numpy()
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return 0.0, 0.0
    mean = math.fsum(v.tolist()) / len(v)
    var = math.fsum(((v - mean) ** 2).tolist()) / len(v)
    return mean, math.sqrt(var)


def days_before_years(on: dt.date, years: np.ndarray) -> np.ndarray:
    """Dias desde 1970 de ``on`` menos ``years`` anos (29/02 vira 28/02 em ano não bissexto)."""
    yr = (on.year - years).astype(np.int64)
    month_start = (yr - 1970).astype("datetime64[Y]").astype("datetime64[M]") + np.timedelta64(on.month - 1, "M")
    start = month_start.astype("datetime64[D]")
    month_len = ((month_start + np.timedelta64(1, "M")).astype("datetime64[D]") - start).astype(np.int64)
    return start.astype(np.int64) + np.minimum(on.day, month_len) - 1


class _BirthdateJob(Job):
    def __init__(self, n: int, ages: np.ndarray, on: dt.date, age_validity: np.ndarray | None) -> None:
        self.ages = np.ascontiguousarray(ages, np.int64)
        top = int(ages.max()) if len(ages) else 0
        edges = days_before_years(on, np.arange(top + 2)).astype(np.int64)
        self.upper = np.ascontiguousarray(edges)  # último dia possível para a idade a: edges[a]
        self.lower = np.ascontiguousarray(edges[1:] + 1)  # primeiro dia possível: edges[a + 1] + 1
        self.out = np.empty(n, np.int32)
        self.age_validity = age_validity

    def fill(self, block: Block, state: np.ndarray) -> None:
        a, m = block.start, block.rows
        lib().dg_birthdate(ptr(state), ptr(self.ages[a:]), ptr(self.lower), ptr(self.upper), m, ptr(self.out[a:]))

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        return primitive_to_series(self.out, name, _and(validity, self.age_validity), arrow_type("date"))


@registry.register
class BirthdateProvider(Provider[BirthdateConfig]):
    kind = "birthdate"
    config_cls = BirthdateConfig
    inputs = ("age",)
    ns_per_row = 5.0

    def plan(self, run: Run, config: BirthdateConfig, inputs: Mapping[str, Any]) -> Job:
        s = as_series(_require(inputs, "age", self.kind), "age", run.n)
        if not s.dtype.is_numeric():
            raise TypeError(f"a coluna de idade deve ser numérica, veio {s.dtype}")
        ages = s.fill_null(0).cast(pl.Int64).to_numpy()
        if len(ages) and int(ages.min()) < 0:
            raise ValueError("a coluna de idade tem valores negativos")
        if len(ages) and int(ages.max()) > config.on.year - 1:
            raise ValueError(f"idade grande demais para a data de referência {config.on}")
        return _BirthdateJob(run.n, ages, config.on, _validity_of(s))


class _CorrelatedJob(Job):
    def __init__(self, n: int, x: np.ndarray, center: float, scale: float, config: CorrelatedConfig) -> None:
        self.x, self.center, self.scale = x, center, scale
        self.a = config.std * config.rho
        self.b = config.std * math.sqrt(max(0.0, 1.0 - config.rho * config.rho))
        self.mean = config.mean
        self.lognormal = config.lognormal
        self.out = np.empty(n, np.float64)

    def fill(self, block: Block, state: np.ndarray) -> None:
        a, m = block.start, block.rows
        # no C++: o exp é o determinístico (o np.exp muda o último bit conforme a CPU e o sistema)
        lib().dg_correlated(ptr(state), ptr(self.x[a:]), self.center, self.scale, self.a, self.b, self.mean,
                            int(self.lognormal), m, ptr(self.out[a:]))  # fmt: skip

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        return primitive_to_series(self.out, name, validity)


@registry.register
class CorrelatedProvider(Provider[CorrelatedConfig]):
    kind = "correlated"
    config_cls = CorrelatedConfig
    inputs = ("other",)
    ns_per_row = 5.0

    def plan(self, run: Run, config: CorrelatedConfig, inputs: Mapping[str, Any]) -> Job:
        s = as_series(_require(inputs, "other", self.kind), "other", run.n)
        if not (s.dtype.is_numeric() or s.dtype == pl.Boolean):
            raise TypeError(f"a coluna 'other' deve ser numérica, veio {s.dtype}")
        x = s.cast(pl.Float64)
        center, scale = config.center, config.scale
        if center is None or scale is None:
            mean, sd = sample_moments(x)
            center = mean if center is None else center
            scale = sd if scale is None else scale
        xs = np.ascontiguousarray(x.fill_null(center).fill_nan(center).to_numpy(), np.float64)
        return _CorrelatedJob(run.n, xs, center, scale if scale > 0 else 0.0, config)


class _ChoiceByJob(Job):
    def __init__(self, n: int, group: np.ndarray, edges: np.ndarray, vocab: Vocabulary, valid: np.ndarray | None):
        self.group = group  # grupo de cada linha (float64, para somar com o sorteio)
        self.edges = edges  # g + acumulado normalizado de cada opção, grupo a grupo
        self.vocab = vocab
        self.valid = valid
        self.views = np.empty((n, 4), np.uint32)

    def fill(self, block: Block, state: np.ndarray) -> None:
        a, m = block.start, block.rows
        u = np.empty(m, np.float64)
        lib().dg_rand_f64(ptr(state), 0.0, 1.0, m, ptr(u))
        u += self.group[a : a + m]
        idx = np.searchsorted(self.edges, u, side="right").astype(np.uint32)
        np.minimum(idx, np.uint32(len(self.vocab) - 1), out=idx)  # g + u arredondado para g + 1 (raríssimo)
        lib().dg_gather_views(ptr(self.vocab.views), ptr(idx), m, ptr(self.views[a:]))

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        return views_to_series(self.views, self.vocab.data, name, _and(validity, self.valid), trim_data=False)


@registry.register
class ChoiceByProvider(Provider[ChoiceByConfig]):
    kind = "choice_by"
    config_cls = ChoiceByConfig
    inputs = ("by",)
    ns_per_row = 8.0

    def plan(self, run: Run, config: ChoiceByConfig, inputs: Mapping[str, Any]) -> Job:
        s = as_series(_require(inputs, "by", self.kind), "by", run.n)
        keys = list(config.options)
        groups = [config.options[k] for k in keys]
        if config.default is not None:
            groups.append(config.default)
        missing = len(keys)  # valores fora de options (e nulos): grupo do default, se houver
        g = np.asarray(
            s.cast(pl.String)
            .replace_strict(keys, list(range(len(keys))), default=missing, return_dtype=pl.UInt32)
            .fill_null(missing)
            .to_numpy()
        )
        valid = None
        if config.default is None and (g == missing).any():
            mask = g != missing
            packed = np.zeros(-(-run.n // 64) * 8, np.uint8)
            p = np.packbits(mask, bitorder="little")
            packed[: len(p)] = p
            valid = packed.view(np.uint64)
            g = np.where(mask, g, 0)
        values: list[str] = []
        edges: list[float] = []
        for gi, (vals, weights) in enumerate(groups):
            w = np.ones(len(vals)) if weights is None else np.asarray(weights, np.float64)
            cum = np.cumsum(w) / math.fsum(w.tolist())
            cum[-1] = 1.0
            edges.extend(gi + cum)
            values.extend(vals)
        return _ChoiceByJob(run.n, g.astype(np.float64), np.asarray(edges), Vocabulary.from_strings(values), valid)
