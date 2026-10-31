"""Endereços do CNEFE (IBGE, Censo 2022): CEP, endereço (struct), cidade e UF.

Cada linha sorteia um trecho de rua (CEP x logradouro) com peso = número de endereços. Daí em diante tudo é cópia de
views no C++: o nome da rua, do bairro, da cidade e da UF vêm das tabelas de nomes (`ViewTable`), sem montar texto
em Python nem em Polars, e o CEP é formatado direto do UInt32 na view. Por isso escala com as threads (no MVP, o
``gather`` + ``str.slice`` + ``concat_str`` do Polars rodava numa thread só).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import polars as pl

from .._native import lib, ptr
from ..config.address import AddressConfig, CepConfig, CityConfig, StateConfig
from ..core.arrow import apply_validity, numeric_to_series, primitive_to_series, views_to_series
from ..core.blocks import Block
from ..core.tables import ViewTable, alias_table
from ..locales import Locale
from ..registry import registry
from .base import Job, Provider, Run, TextJob, probability_threshold
from .choice import ViewsChoiceJob, cached_alias, vocabulary

__all__ = ["AddressJob", "address_tables"]

FULL_SEPARATORS = (", ", " - ", ", ", " - ", ", ")  # rua, número - bairro, cidade - UF, CEP


def _states(locale: Locale) -> list[str]:
    return sorted(locale.states())


def _names(locale: Locale, source: str) -> dict[str, Any]:
    """Tabelas de nomes da base (ruas, bairros, municípios, UFs) e a UF de cada trecho; em cache por base."""
    base = locale.addresses(source)

    def build() -> dict[str, Any]:
        mun = locale.municipalities()
        states = _states(locale)
        pos = {u: i for i, u in enumerate(states)}
        mun_uf = np.array([pos[u] for u in mun.ufs], np.uint32)
        row_uf = np.ascontiguousarray(mun_uf[base.city])
        return {
            "base": base,
            "rec": _records(base, row_uf),
            "streets": ViewTable.from_series(base.streets),
            "districts": ViewTable.from_series(base.districts),
            "cities": ViewTable.from_strings(mun.names),
            "states": ViewTable.from_strings(states),
            "row_uf": row_uf,
            "uf_pos": pos,
        }

    return locale.cached(("address_names", base.source), build)


# campos do registro de cada trecho (REC_U32 = 8 inteiros de 32 bits em address.cpp)
REC_CEP, REC_STREET, REC_DISTRICT, REC_CITY, REC_UF, REC_NUM_MIN, REC_NUM_MAX = range(7)


def _records(base: Any, row_uf: np.ndarray) -> np.ndarray:
    """Um registro de 32 bytes por trecho com tudo o que o endereço lê dele: o sorteio busca um registro só na memória
    (meia linha de cache) em vez de um valor em cada array, o que pesa na base completa (4 milhões de trechos)."""
    rec = np.zeros((len(base), 8), np.uint32)
    rec[:, REC_CEP] = base.cep
    rec[:, REC_STREET] = base.street
    rec[:, REC_DISTRICT] = base.district
    rec[:, REC_CITY] = base.city
    rec[:, REC_UF] = row_uf
    if base.number_min is not None and base.number_max is not None:
        rec[:, REC_NUM_MIN] = base.number_min.astype(np.int32).view(np.uint32)
        rec[:, REC_NUM_MAX] = base.number_max.astype(np.int32).view(np.uint32)
    return rec


def address_tables(locale: Locale, source: str, ufs: tuple[str, ...] | None) -> dict[str, Any]:
    """Nomes + tabela alias dos trechos (só das UFs pedidas)."""
    names = _names(locale, source)

    def build() -> dict[str, Any]:
        base, pos = names["base"], names["uf_pos"]
        w = base.weight
        if ufs is not None:
            bad = sorted(set(ufs) - set(pos))
            if bad:
                raise ValueError(f"UF desconhecida: {', '.join(bad)}")
            w = w * np.isin(names["row_uf"], [pos[u] for u in ufs])
            if not w.any():
                raise ValueError(f"a base {base.source!r} não tem endereços de {', '.join(ufs)}")
        return {**names, "tab": alias_table(w), "k": len(w)}

    return locale.cached(("address_tables", names["base"].source, ufs), build)


# ------------------------------------------------------------------ CEP
@registry.register
class CepProvider(Provider[CepConfig]):
    kind = "cep"
    config_cls = CepConfig
    ns_per_row = 4.0

    def plan(self, run: Run, config: CepConfig, inputs: Mapping[str, Any]) -> Job:
        t = address_tables(run.locale, config.source, config.uf)
        fn, k, fmt = lib().dg_cep_pick, t["k"], int(config.formatted)
        tab, ceps = ptr(t["tab"]), ptr(t["base"].cep)
        # "01310-100" tem 9 caracteres: cabe na view, sem buffer de texto
        return TextJob(run.n, 0, lambda st, m, v, d, _: fn(st, k, tab, ceps, fmt, m, v), len(run.blocks))


# ------------------------------------------------------------------ endereço
def _phone_tables(locale: Locale) -> dict[str, Any]:
    """DDDs de todas as UFs (2 caracteres ASCII em uint16) e, por UF (na ordem de `_states`), os índices dos dela."""

    def build() -> dict[str, Any]:
        states = locale.states()
        order = _states(locale)
        codes = [d for u in order for d in states[u].area_codes]
        chars = np.array([ord(str(d)[0]) | (ord(str(d)[1]) << 8) for d in codes], np.uint16)
        cnt = np.array([len(states[u].area_codes) for u in order], np.uint32)
        off = np.concatenate([[0], np.cumsum(cnt)[:-1]]).astype(np.uint32)
        return {"chars": chars, "off": off, "cnt": cnt, "flat": np.arange(len(codes), dtype=np.uint32),
                "tab": alias_table(np.ones(len(codes)))}  # fmt: skip

    return locale.cached("address_phone", build)


class AddressJob(Job):
    """Índice do trecho por linha + uma coluna de views (ou de números) por campo do struct."""

    def __init__(self, run: Run, config: AddressConfig) -> None:
        n = run.n
        self.n, self.config = n, config
        self.t = address_tables(run.locale, config.source, config.uf)
        base = self.t["base"]
        self.lo, self.hi = base.number_min, base.number_max
        self.idx = np.empty(n, np.uint32)
        self.number = np.empty(n, np.int32)
        self.views = {f: np.empty((n, 4), np.uint32) for f in ("street", "neighborhood", "city", "state", "cep")}
        self.complements = vocabulary(run.locale.address_complements())
        self.views["complement"] = np.empty((n, 4), np.uint32)
        self.number_states = run.states(":number")  # cada campo sorteado tem fluxo próprio (o do trecho é o da coluna)
        self.complement_states = run.states(":complement")
        self.complement_valid = run.bits(config.complement, ":complement_null") if config.complement < 1 else None
        self.phone = _phone_tables(run.locale) if config.phone else None
        if self.phone is not None:
            self.views["phone"] = np.empty((n, 4), np.uint32)
            self.phone_states = run.states(":phone")
            self.ddd_states = run.states(":phone_ddd")
            self.phone_datas: list[np.ndarray] = [np.empty(0, np.uint8)] * len(run.blocks)
        if config.full:
            self.views["full"] = np.empty((n, 4), np.uint32)
            self.full_datas: list[np.ndarray] = [np.empty(0, np.uint8)] * len(run.blocks)
            seps = "".join(FULL_SEPARATORS).encode("utf-8")
            self.seps = np.frombuffer(seps + b"\0" * 8, np.uint8).copy()  # folga: o kernel copia 8 bytes por separador
            # sep_off[0] = 0 e sep_off[p] = fim do separador entre as partes p-1 e p (k entradas para k partes)
            self.sep_off = np.cumsum([0, *(len(s.encode("utf-8")) for s in FULL_SEPARATORS)]).astype(np.uint32)

    def fill(self, block: Block, state: np.ndarray) -> None:
        t, dg = self.t, lib()
        a, m = block.start, block.rows
        v = {f: arr[a : a + m] for f, arr in self.views.items()}
        small = np.empty((m, 4), np.uint32)  # por linha: número mínimo, número máximo e UF do trecho
        dg.dg_address_core(
            ptr(state), t["k"], ptr(t["tab"]), ptr(t["rec"]), ptr(t["streets"].views), ptr(t["districts"].views),
            ptr(t["cities"].views), ptr(t["states"].views), m, ptr(self.idx[a:]), ptr(small), ptr(v["street"]),
            ptr(v["neighborhood"]), ptr(v["city"]), ptr(v["state"]), ptr(v["cep"]),
        )  # fmt: skip
        dg.dg_house_number(ptr(self.number_states[block.index]), ptr(small), m, ptr(self.number[a:]))
        comp, cst = self.complements, self.complement_states[block.index]
        dg.dg_choice_views(ptr(comp.views), len(comp), ptr(cst), m, ptr(v["complement"]))
        if self.phone is not None:
            self._phone(block, small, v["phone"])
        if self.config.full:
            self._full(block, v)

    def _phone(self, block: Block, small: np.ndarray, out: np.ndarray) -> None:
        p, dg, m = self.phone, lib(), block.rows
        assert p is not None
        st = self.phone_states[block.index]
        ddd = np.empty(m, np.uint32)
        dst = self.ddd_states[block.index]
        dg.dg_pick_in_group(ptr(dst), ptr(small), 2, ptr(p["off"]), ptr(p["cnt"]), ptr(p["flat"]), m,
                           ptr(ddd))  # fmt: skip
        data = np.empty(m * 16, np.uint8)
        thr = probability_threshold(0.8)
        dg.dg_phone_views(ptr(st), len(p["chars"]), ptr(p["tab"]), ptr(p["chars"]), thr, 1, m, ptr(out), ptr(data),
                         ptr(ddd))  # fmt: skip
        dg.dg_views_used(ptr(out), m, block.index)
        self.phone_datas[block.index] = data

    def _full(self, block: Block, v: dict[str, np.ndarray]) -> None:
        t, dg, m = self.t, lib(), block.rows
        num = np.empty((m, 4), np.uint32)
        dg.dg_int_views(ptr(self.number[block.start :]), m, ptr(num))
        parts = [(v["street"], t["streets"].datas), (num, ()), (v["neighborhood"], t["districts"].datas),
                 (v["city"], t["cities"].datas), (v["state"], t["states"].datas), (v["cep"], ())]  # fmt: skip
        k = len(parts)
        views_p = np.array([ptr(p[0]) for p in parts], np.uintp)
        buf_lists = [np.array([ptr(d) for d in p[1]] or [0], np.uintp) for p in parts]
        bufs_p = np.array([ptr(b) for b in buf_lists], np.uintp)
        size = dg.dg_concat_size(m, k, ptr(views_p), ptr(self.sep_off))
        data = np.empty(size + 16, np.uint8)
        dg.dg_concat_views(m, k, ptr(views_p), ptr(bufs_p), ptr(self.seps), ptr(self.sep_off), ptr(v["full"]),
                          ptr(data))  # fmt: skip
        dg.dg_views_used(ptr(v["full"]), m, block.index)
        self.full_datas[block.index] = data[:size]

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        t, base, vw = self.t, self.t["base"], self.views

        def text(field: str, datas: Any, valid: np.ndarray | None = None) -> pl.Series:
            return views_to_series(vw[field], list(datas) or None, field, valid, trim_data=False)

        cols = [
            text("street", t["streets"].datas),
            primitive_to_series(self.number, "number"),
            text(
                "complement", () if self.complements.data is None else (self.complements.data,), self.complement_valid
            ),
            text("neighborhood", t["districts"].datas),
            text("city", t["cities"].datas),
            text("state", t["states"].datas),
            text("cep", ()),
        ]
        if self.phone is not None:
            cols.append(text("phone", self.phone_datas))
        if self.config.coords:
            if base.lat is None or base.lon is None:
                raise ValueError(f"a base {base.source!r} não tem coordenadas")
            scale = base.coord_scale
            cols.append(numeric_to_series(base.lat[self.idx] / scale, "latitude"))
            cols.append(numeric_to_series(base.lon[self.idx] / scale, "longitude"))
        if self.config.full:
            cols.append(text("full", self.full_datas))
        return apply_validity(pl.DataFrame(cols).to_struct(name), validity)


@registry.register
class AddressProvider(Provider[AddressConfig]):
    kind = "address"
    config_cls = AddressConfig
    ns_per_row = 40.0

    def plan(self, run: Run, config: AddressConfig, inputs: Mapping[str, Any]) -> Job:
        return AddressJob(run, config)


# ------------------------------------------------------------------ cidade e UF
@registry.register
class CityProvider(Provider[CityConfig]):
    kind = "city"
    config_cls = CityConfig
    ns_per_row = 3.6

    def plan(self, run: Run, config: CityConfig, inputs: Mapping[str, Any]) -> Job:
        mun = run.locale.municipalities()
        w = mun.population
        if config.uf is not None:
            bad = sorted(set(config.uf) - set(run.locale.states()))
            if bad:
                raise ValueError(f"UF desconhecida: {', '.join(bad)}")
            w = w * np.isin(np.array(mun.ufs), config.uf)
        names = tuple(f"{c}/{u}" for c, u in zip(mun.names, mun.ufs, strict=True)) if config.with_state else mun.names
        return ViewsChoiceJob(run.n, vocabulary(names), cached_alias(tuple(w.tolist())))


@registry.register
class StateProvider(Provider[StateConfig]):
    kind = "state"
    config_cls = StateConfig
    ns_per_row = 3.6

    def plan(self, run: Run, config: StateConfig, inputs: Mapping[str, Any]) -> Job:
        states = run.locale.states()
        order = _states(run.locale)
        tab = cached_alias(tuple(float(states[u].population) for u in order)) if config.weighted else None
        return ViewsChoiceJob(run.n, vocabulary(tuple(order)), tab)
