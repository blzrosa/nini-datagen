"""Sexo, idade e nomes (primeiro nome, sobrenome, nome completo)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

from .._native import lib, ptr
from ..config.person import AgeConfig, FirstNameConfig, FullNameConfig, LastNameConfig, SexConfig
from ..core.arrow import string_view_buffers, views_to_series
from ..core.blocks import Block, map_blocks
from ..core.rng import block_states
from ..core.tables import Vocabulary, alias_table
from ..locales import FirstNames, Locale
from ..registry import registry
from .base import ArrayJob, Context, Job, Provider, Run, probability_threshold
from .choice import ViewsChoiceByJob, ViewsChoiceJob, cached_alias, vocabulary

__all__ = ["female_mask"]


@registry.register
class SexProvider(Provider[SexConfig]):
    kind = "sex"
    config_cls = SexConfig
    ns_per_row = 4.3

    def plan(self, run: Run, config: SexConfig, inputs: Mapping[str, Any]) -> Job:
        p = run.locale.p_female if config.p_female is None else config.p_female
        return ViewsChoiceJob(run.n, vocabulary(config.labels), cached_alias((p, 1.0 - p)))


@registry.register
class AgeProvider(Provider[AgeConfig]):
    kind = "age"
    config_cls = AgeConfig
    ns_per_row = 2.1

    def plan(self, run: Run, config: AgeConfig, inputs: Mapping[str, Any]) -> Job:
        low, k = config.low, config.high - config.low + 1
        if config.weights is not None:
            tab = cached_alias(config.weights)
        else:
            loc, high = run.locale, config.high
            tab = loc.cached(("age", low, high), lambda: alias_table(loc.age_weights(low, high)))
        fn = lib().dg_alias_idx

        def kernel(st: int, m: int, o: int) -> None:
            fn(k, tab.ctypes.data, st, m, o)  # escreve o índice (0..k-1) no buffer int32

        def to_age(seg: np.ndarray) -> None:
            seg += np.int32(low)

        return ArrayJob(run.n, np.int32, kernel, post=to_age if low else None)


# ---------------------------------------------------------------------------------------------- nomes


@dataclass(frozen=True, eq=False)
class _NamePools:
    """Vocabulários e tabelas alias dos primeiros nomes, montados uma vez por locale."""

    all: Vocabulary
    all_tab: np.ndarray
    by_sex: Vocabulary  # femininos em [0, kf), masculinos em [kf, kf + km)
    by_sex_tab: np.ndarray
    kf: int


def _build_pools(d: FirstNames, keep: np.ndarray | None = None) -> _NamePools:
    names = np.array(d.names, dtype=object)
    keep = np.ones(len(names), dtype=bool) if keep is None else keep
    fem, mas = keep & (d.female > 0), keep & (d.male > 0)
    by_sex = Vocabulary.from_strings([*names[fem], *names[mas]])
    tab = np.concatenate([alias_table(d.female[fem]), alias_table(d.male[mas])])
    return _NamePools(vocabulary(tuple(names[keep])), alias_table(d.total[keep]), by_sex, tab, int(fem.sum()))


def _name_pools(locale: Locale) -> _NamePools:
    return locale.cached("first_name_pools", lambda: _build_pools(locale.first_names()))


def _prefix_pools(locale: Locale) -> tuple[_NamePools, np.ndarray]:
    """Primeiros elementos de prenome composto (Maria, Ana, João, José...), com a frequência de cada um por sexo, e o
    índice de cada um no vocabulário por sexo de `_name_pools` (para comparar e juntar por índice)."""

    def build() -> tuple[_NamePools, np.ndarray]:
        d = locale.first_names()
        names = np.array(d.names, dtype=object)
        fem, mas = locale.compound_prefixes()
        keep_f, keep_m = np.isin(names, fem), np.isin(names, mas)
        female = np.where(keep_f, d.female, 0.0)
        male = np.where(keep_m, d.male, 0.0)
        pools = _build_pools(FirstNames(d.names, female + male, female, male), keep_f | keep_m)
        main = _name_pools(locale)
        where_f = {x: i for i, x in enumerate(main.by_sex.strings[: main.kf])}
        where_m = {x: main.kf + i for i, x in enumerate(main.by_sex.strings[main.kf :])}
        to_main = np.array(
            [where_f[x] if i < pools.kf else where_m[x] for i, x in enumerate(pools.by_sex.strings)], dtype=np.uint32
        )
        return pools, to_main

    return locale.cached("compound_prefix_pools", build)


def female_mask(sex: Any, run: Run, p_female: float) -> np.ndarray:
    """Coluna de sexo -> uint8 (1 = feminino) pela primeira letra (F.../M..., sem diferenciar maiúsculas).

    Valores nulos ou que não começam com F/M são sorteados com ``p_female``, num fluxo próprio (``:sex``).
    """
    s = sex if isinstance(sex, pl.Series) else pl.Series(list(sex))
    if len(s) != run.n:
        raise ValueError(f"a coluna de sexo tem {len(s)} valores, mas n = {run.n}")
    if s.dtype != pl.String:  # categorias, Enum...: pelo texto
        s = s.cast(pl.String)
    got = string_view_buffers(s)
    if got is not None:  # caminho rápido: o C++ lê a primeira letra direto das views do Arrow, numa passada
        views, valid, bit_offset, _owner = got
        out = np.empty(run.n, np.uint8)
        valid_ptr = ptr(valid) if valid is not None else None
        unknown = lib().dg_sex_mask(ptr(views), valid_ptr, bit_offset, run.n, ptr(out))
        known = out != 2 if unknown else None
        is_f = out
    else:  # mesma regra em Polars (mais lento)
        first = s.str.slice(0, 1).str.to_uppercase()
        is_f = (first == "F").fill_null(False).to_numpy().astype(np.uint8)
        known = first.is_in(["F", "M"]).fill_null(False).to_numpy()
        known = None if known.all() else known
    if known is not None:
        bits = run.bits(p_female, ":sex")
        drawn = np.unpackbits(bits.view(np.uint8), bitorder="little")[: run.n]
        is_f = np.where(known, is_f, drawn).astype(np.uint8)
    return is_f


def take_sex_input(kwargs: dict[str, Any]) -> dict[str, Any]:
    """``sex="F"``/``"M"``/``None`` é configuração; uma coluna (Series, lista, array) é dado."""
    sex = kwargs.get("sex")
    if sex is None or isinstance(sex, str):
        return {}
    return {"sex": kwargs.pop("sex")}


@registry.register
class FirstNameProvider(Provider[FirstNameConfig]):
    kind = "first_name"
    config_cls = FirstNameConfig
    inputs = ("sex",)
    ns_per_row = 5.4

    def take_inputs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        return take_sex_input(kwargs)

    def pools(self, locale: Locale) -> _NamePools:
        return _name_pools(locale)

    def plan(self, run: Run, config: FirstNameConfig, inputs: Mapping[str, Any]) -> Job:
        pools = self.pools(run.locale)
        kf = pools.kf
        if "sex" in inputs:
            if config.sex is not None:
                raise ValueError("passe sex como letra (configuração) ou como coluna (dados), não os dois")
            is_f = female_mask(inputs["sex"], run, run.locale.p_female)
            return ViewsChoiceByJob(run.n, pools.by_sex, pools.by_sex_tab, kf, is_f)
        if config.sex == "F":
            return ViewsChoiceJob(run.n, pools.by_sex.slice(0, kf), pools.by_sex_tab[:kf])
        if config.sex == "M":
            return ViewsChoiceJob(run.n, pools.by_sex.slice(kf, len(pools.by_sex)), pools.by_sex_tab[kf:])
        return ViewsChoiceJob(run.n, pools.all, pools.all_tab)


@registry.register
class LastNameProvider(Provider[LastNameConfig]):
    kind = "last_name"
    config_cls = LastNameConfig
    ns_per_row = 4.9

    def plan(self, run: Run, config: LastNameConfig, inputs: Mapping[str, Any]) -> Job:
        vocab, tab = _last_pool(run.locale)
        return ViewsChoiceJob(run.n, vocab, tab)


def _last_pool(loc: Locale) -> tuple[Vocabulary, np.ndarray]:
    def build() -> tuple[Vocabulary, np.ndarray]:
        d = loc.last_names()
        return vocabulary(d.names), alias_table(d.weights)

    return loc.cached("last_name_pool", build)


class _Indices:
    """Sorteio de índices num vocabulário por sexo, bloco a bloco, com o mesmo consumo do gerador que a escolha de
    views (`ViewsChoiceJob`/`ViewsChoiceByJob`): a coluna sai idêntica à do `first_name` com o mesmo fluxo."""

    def __init__(self, run: Run, stream: str, pools: _NamePools, sex: str | None, is_f: np.ndarray | None) -> None:
        self.states = block_states(run.ctx.seed, stream, len(run.blocks))
        self.pools, self.sex, self.is_f = pools, sex, is_f
        self.out = np.empty(run.n, np.uint32)

    def fill(self, b: Block) -> None:
        lib_ = lib()
        pools, kf = self.pools, self.pools.kf
        km = len(pools.by_sex) - kf
        st, out = ptr(self.states[b.index]), ptr(self.out[b.start :])
        if self.is_f is not None:
            lib_.dg_alias_idx_by(kf, km, ptr(pools.by_sex_tab), ptr(self.is_f[b.start :]), st, b.rows, out)
        elif self.sex == "F":
            lib_.dg_alias_idx(kf, ptr(pools.by_sex_tab), st, b.rows, out)
        else:
            lib_.dg_alias_idx(km, ptr(pools.by_sex_tab[kf:]), st, b.rows, out)
            self.out[b.start : b.start + b.rows] += np.uint32(kf)


@registry.register
class FullNameProvider(Provider[FullNameConfig]):
    """Composto: prenome + (com probabilidade ``compound``) segundo prenome do mesmo sexo + sobrenome + (com
    probabilidade ``two_surnames``) segundo sobrenome.

    O primeiro elemento de um prenome composto vem dos prefixos comuns do locale (Maria Eduarda, João Pedro); o segundo,
    de todos os nomes do mesmo sexo, com um segundo sorteio se repetir o primeiro (se repetir de novo, fica um prenome
    só). Segundo sobrenome igual ao primeiro também some. Tudo é decidido por índices e o texto é montado de uma vez no
    C++ (`dg_join_views`), bloco a bloco em paralelo.

    Fluxos: ``<nome>.sex`` (sem sexo dado), ``<nome>.first``, ``<nome>.prefix``, ``<nome>.middle`` (e ``:null``),
    ``<nome>.middle2``, ``<nome>.last1``, ``<nome>.last2`` (e ``:null``), ``<nome>:null``.
    """

    kind = "full_name"
    config_cls = FullNameConfig
    inputs = ("sex",)
    ns_per_row = 30.0

    def take_inputs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        return take_sex_input(kwargs)

    def plan(self, run: Run, config: FullNameConfig, inputs: Mapping[str, Any]) -> Job:
        raise NotImplementedError  # composto: monta as partes em `generate`

    def generate(
        self, n: int, config: FullNameConfig, ctx: Context, inputs: Mapping[str, Any] | None = None
    ) -> pl.Series:
        run = self.start(n, config, ctx)
        name, loc = run.name, run.locale
        inputs = inputs or {}
        pools = _name_pools(loc)
        prefix_pools, prefix_to_main = _prefix_pools(loc)
        sex = config.sex
        is_f: np.ndarray | None = None
        if "sex" in inputs:
            if sex is not None:
                raise ValueError("passe sex como letra (configuração) ou como coluna (dados), não os dois")
            is_f = female_mask(inputs["sex"], run, loc.p_female)
        elif sex is None:  # os dois prenomes precisam do mesmo sexo: sorteia um por linha (como `sex`)
            sex_idx = _Draw(run, f"{name}.sex", cached_alias((loc.p_female, 1.0 - loc.p_female)))
            map_blocks(sex_idx.fill, run.blocks, 1)
            is_f = (sex_idx.out == 0).view(np.uint8)

        first = _Indices(run, f"{name}.first", pools, sex, is_f)
        prefix = _Indices(run, f"{name}.prefix", prefix_pools, sex, is_f)
        middle = _Indices(run, f"{name}.middle", pools, sex, is_f)
        middle2 = _Indices(run, f"{name}.middle2", pools, sex, is_f)
        last_vocab, last_tab = _last_pool(loc)
        last1 = _Draw(run, f"{name}.last1", last_tab)
        last2 = _Draw(run, f"{name}.last2", last_tab)
        threads = ctx.threads

        def draw(b: Block) -> None:
            for part in (first, prefix, middle, middle2, last1, last2):
                part.fill(b)

        map_blocks(draw, run.blocks, threads)
        compound = _presence(run, f"{name}.middle", config.compound)
        second_surname = _presence(run, f"{name}.last2", config.two_surnames)

        # decisões por índice (nomes são únicos no vocabulário: índice igual <=> texto igual)
        empty_given, empty_last = np.uint32(len(pools.by_sex)), np.uint32(len(last_vocab))
        g1 = np.where(compound, prefix_to_main[prefix.out], first.out).astype(np.uint32)
        g2 = np.where(middle.out != g1, middle.out, middle2.out)
        g2 = np.where(compound & (g2 != g1), g2, empty_given).astype(np.uint32)
        l1 = last1.out
        l2 = np.where(second_surname & (last2.out != l1), last2.out, empty_last).astype(np.uint32)

        parts = [(pools.by_sex, g1), (pools.by_sex, g2), (last_vocab, l1), (last_vocab, l2)]
        views, datas = join_text(run, parts, " ", threads)
        return views_to_series(views, datas, name, self.validity(run, config))


def join_text(
    run: Run, parts: list[tuple[Vocabulary, np.ndarray]], sep: str, threads: int | None
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Monta ``parte1 sep parte2 ...`` para cada linha, no C++, bloco a bloco (cada bloco com seu buffer de texto).

    Cada parte é ``(vocabulário, índice por linha)``; o índice ``len(vocabulário)`` quer dizer "parte vazia" (pulada,
    sem separador). Devolve as views e a lista de buffers (um por bloco), prontas para `views_to_series`.
    """
    pad = np.zeros(16, np.uint8)
    # o kernel copia em pedaços de 16 bytes: uma view vazia no fim de cada vocabulário (é a "parte vazia" e também a
    # folga de leitura dos textos curtos) e 16 bytes de folga depois de cada texto
    dvs = [np.vstack([v.views, np.zeros((1, 4), np.uint32)]) for v, _ in parts]
    texts = [pad if v.data is None else np.concatenate([v.data, pad]) for v, _ in parts]
    idxs = [np.ascontiguousarray(i, dtype=np.uint32) for _, i in parts]
    dv_ptrs = np.array([ptr(d) for d in dvs], dtype=np.uint64)
    data_ptrs = np.array([ptr(t) for t in texts], dtype=np.uint64)
    sep_bytes = np.frombuffer(sep.encode("utf-8") + bytes(16), np.uint8).copy()
    seplen = len(sep.encode("utf-8"))
    views = np.empty((run.n, 4), np.uint32)
    datas: list[np.ndarray] = [np.empty(0, np.uint8)] * len(run.blocks)

    def join(b: Block) -> None:
        lib_ = lib()
        idx_ptrs = np.array([ptr(i[b.start :]) for i in idxs], dtype=np.uint64)
        size = lib_.dg_join_size(b.rows, len(parts), ptr(dv_ptrs), ptr(idx_ptrs), seplen)
        buf = np.empty(size + 16, np.uint8)
        lib_.dg_join_views(
            b.rows, len(parts), ptr(dv_ptrs), ptr(data_ptrs), ptr(idx_ptrs), ptr(sep_bytes), seplen, b.index,
            ptr(views[b.start :]), ptr(buf),
        )  # fmt: skip
        datas[b.index] = buf[:size]

    map_blocks(join, run.blocks, threads)
    return views, datas


class _Draw:
    """Índices de um sorteio ponderado (alias), bloco a bloco: mesmo consumo do gerador que `ViewsChoiceJob`."""

    def __init__(self, run: Run, stream: str, tab: np.ndarray) -> None:
        self.states = block_states(run.ctx.seed, stream, len(run.blocks))
        self.tab = tab
        self.out = np.empty(run.n, np.uint32)

    def fill(self, b: Block) -> None:
        lib().dg_alias_idx(len(self.tab), ptr(self.tab), ptr(self.states[b.index]), b.rows, ptr(self.out[b.start :]))


def _presence(run: Run, stream: str, p: float) -> np.ndarray:
    """Máscara booleana "a parte existe", com os mesmos bits que ``null_fraction = 1 - p`` daria no fluxo ``stream``."""
    null_fraction = 1.0 - p
    if null_fraction <= 0.0:
        return np.ones(run.n, dtype=bool)
    bits = _bits(run, stream + ":null", 1.0 - null_fraction)
    return np.unpackbits(bits.view(np.uint8), bitorder="little")[: run.n].astype(bool)


def _bits(run: Run, stream: str, p: float) -> np.ndarray:
    """Bits Bernoulli(p) do fluxo ``stream`` (como `Run.bits`, para um fluxo com outro nome)."""
    out = np.empty(-(-run.n // 64), np.uint64)
    st = block_states(run.ctx.seed, stream, len(run.blocks))
    thr = probability_threshold(p)
    for b in run.blocks:
        lib().dg_bool_bits(ptr(st[b.index]), thr, b.rows, ptr(out[b.start // 64 :]))
    return out
