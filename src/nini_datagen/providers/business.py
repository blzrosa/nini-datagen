"""Empresa (razão social), veículo (marca, modelo e ano coerentes) e profissão."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import polars as pl

from .._native import lib, ptr
from ..config.business import CompanyConfig, OccupationConfig, VehicleConfig
from ..core.arrow import apply_validity, primitive_to_series, views_to_series
from ..core.blocks import Block
from ..core.memory import empty
from ..core.tables import Vocabulary, alias_table
from ..locales import Locale
from ..registry import registry
from .base import Job, Provider, Run, TextJob
from .choice import ViewsChoiceJob, cached_alias, vocabulary
from .contact import pack_words

__all__ = ["VehicleJob"]


# ------------------------------------------------------------------ empresa
def _company_tables(locale: Locale) -> dict[str, Any]:
    def build() -> dict[str, Any]:
        last = locale.last_names()
        sectors, brands, types = locale.company_parts()
        parts = {
            "s": (last.names, last.weights),
            "b": (brands, np.ones(len(brands))),
            "r": (sectors, np.ones(len(sectors))),
            "t": (types.names, types.weights),
        }
        out: dict[str, Any] = {}
        for key, (words, w) in parts.items():
            ch, ln = pack_words(list(words), limit=31)
            out[key] = (len(words), ch, ln, alias_table(w))
        ls, lb = int(out["s"][2].max()), int(out["b"][2].max())
        # maior razão social: (2 sobrenomes com " & " ou 2 marcas) + ramo + tipo
        out["max_len"] = max(2 * ls + 3, 2 * lb + 1) + 1 + int(out["r"][2].max()) + 1 + int(out["t"][2].max())
        return out

    return locale.cached("company", build)


@registry.register
class CompanyProvider(Provider[CompanyConfig]):
    kind = "company"
    config_cls = CompanyConfig
    ns_per_row = 20.0

    def plan(self, run: Run, config: CompanyConfig, inputs: Mapping[str, Any]) -> Job:
        t = _company_tables(run.locale)
        args = tuple(x for key in "sbrt" for x in (t[key][0], ptr(t[key][1]), ptr(t[key][2]), ptr(t[key][3])))
        fn = lib().dg_empresa_views
        # textos em sequência; 32 bytes de folga: o kernel copia 32 bytes por palavra
        return TextJob(
            run.n, t["max_len"], lambda st, m, v, d, _: fn(st, *args, m, v, d), len(run.blocks), packed=True, slack=32
        )


# ------------------------------------------------------------------ veículo
def _vehicle_tables(locale: Locale, low: int, high: int) -> dict[str, Any]:
    def build() -> dict[str, Any]:
        v = locale.vehicles()
        cnt = np.array([len(m.names) for m in v.models], np.uint32)
        off = np.concatenate([[0], np.cumsum(cnt)[:-1]]).astype(np.uint32)
        years = np.arange(low, high + 1, dtype=np.int32)
        return {
            "brands": Vocabulary.from_strings(v.brands.names),
            "models": Vocabulary.from_strings([n for m in v.models for n in m.names]),
            "btab": alias_table(v.brands.weights),
            "mtabs": np.concatenate([alias_table(m.weights) for m in v.models]),
            "cnt": cnt,
            "off": off,
            "years": years,
            "ytab": alias_table(np.linspace(1.0, 4.0, len(years))),
        }

    return locale.cached(("vehicles", low, high), build)


class VehicleJob(Job):
    """Índices de marca, modelo (global) e ano por linha; no fim, monta o struct ``{brand, model, year}``."""

    def __init__(self, n: int, t: dict[str, Any]) -> None:
        self.n, self.t = n, t
        self.idx = empty((3, n), np.uint32)

    def fill(self, block: Block, state: np.ndarray) -> None:
        t, a = self.t, block.start
        lib().dg_veiculo_idx(
            ptr(state), len(t["cnt"]), ptr(t["btab"]), ptr(t["off"]), ptr(t["cnt"]), ptr(t["mtabs"]),
            len(t["years"]), ptr(t["ytab"]), block.rows,
            ptr(self.idx[0, a:]), ptr(self.idx[1, a:]), ptr(self.idx[2, a:]),
        )  # fmt: skip

    def _strings(self, vocab: Vocabulary, idx: np.ndarray, name: str) -> pl.Series:
        views = empty((self.n, 4), np.uint32)
        lib().dg_gather_views(ptr(vocab.views), ptr(idx), self.n, ptr(views))
        return views_to_series(views, vocab.data, name, trim_data=False)

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        t = self.t
        brand = self._strings(t["brands"], self.idx[0], "brand")
        model = self._strings(t["models"], self.idx[1], "model")
        year = primitive_to_series(t["years"][self.idx[2]], "year")
        s = pl.DataFrame([brand, model, year]).to_struct(name)
        return apply_validity(s, validity)


@registry.register
class VehicleProvider(Provider[VehicleConfig]):
    kind = "vehicle"
    config_cls = VehicleConfig
    ns_per_row = 8.0

    def plan(self, run: Run, config: VehicleConfig, inputs: Mapping[str, Any]) -> Job:
        return VehicleJob(run.n, _vehicle_tables(run.locale, config.year_low, config.year_high))


# ------------------------------------------------------------------ profissão
@registry.register
class OccupationProvider(Provider[OccupationConfig]):
    kind = "occupation"
    config_cls = OccupationConfig
    ns_per_row = 3.6

    def plan(self, run: Run, config: OccupationConfig, inputs: Mapping[str, Any]) -> Job:
        values = run.locale.occupations()
        weights = tuple((1.0 / np.arange(1, len(values) + 1) ** config.zipf).tolist())
        return ViewsChoiceJob(run.n, vocabulary(values), cached_alias(weights))
