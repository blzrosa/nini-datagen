"""Escolha em lista (com ou sem pesos) e os jobs de escolha reaproveitados por sexo, nomes e sobrenomes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

import numpy as np
import polars as pl

from .._native import lib, ptr
from ..config.choice import ChoiceConfig
from ..core.arrow import bits_to_series, primitive_to_series, views_to_series
from ..core.blocks import Block
from ..core.memory import empty
from ..core.tables import Vocabulary, alias_table
from ..registry import registry
from .base import Job, Provider, Run

__all__ = ["ChoiceProvider", "IndexChoiceJob", "ViewsChoiceByJob", "ViewsChoiceJob", "vocabulary"]


@lru_cache(maxsize=64)
def vocabulary(values: tuple[str, ...]) -> Vocabulary:
    """Vocabulário de uma lista de textos (em cache: listas iguais montam uma vez só)."""
    return Vocabulary.from_strings(values)


@lru_cache(maxsize=64)
def cached_alias(weights: tuple[float, ...]) -> np.ndarray:
    tab = alias_table(weights)
    tab.setflags(write=False)
    return tab


class ViewsChoiceJob(Job):
    """Textos: copia a view (16 bytes) da opção sorteada; todas as linhas apontam para o texto do vocabulário."""

    def __init__(self, n: int, vocab: Vocabulary, tab: np.ndarray | None) -> None:
        self.views = empty((n, 4), np.uint32)
        self.vocab = vocab
        self.tab = tab

    def fill(self, block: Block, state: np.ndarray) -> None:
        out = ptr(self.views[block.start :])
        dv, k = ptr(self.vocab.views), len(self.vocab)
        if self.tab is None:
            lib().dg_choice_views(dv, k, ptr(state), block.rows, out)
        else:
            lib().dg_choice_alias_views(dv, k, ptr(self.tab), ptr(state), block.rows, out)

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        return views_to_series(self.views, self.vocab.data, name, validity, trim_data=False)


class ViewsChoiceByJob(ViewsChoiceJob):
    """Como `ViewsChoiceJob`, com dois grupos (ex.: nomes femininos e masculinos) escolhidos linha a linha por
    ``group0`` (1 = primeiro grupo). O vocabulário tem o grupo 0 nas posições ``[0, k0)`` e o 1 em ``[k0, k0 + k1)``;
    ``tab`` junta as duas tabelas alias, na mesma ordem."""

    def __init__(self, n: int, vocab: Vocabulary, tab: np.ndarray, k0: int, group0: np.ndarray) -> None:
        super().__init__(n, vocab, tab)
        self.tab_by = tab  # sempre presente aqui (no pai, None quer dizer escolha uniforme)
        self.k0, self.k1 = k0, len(vocab) - k0
        self.group0 = np.ascontiguousarray(group0, dtype=np.uint8)

    def fill(self, block: Block, state: np.ndarray) -> None:
        lib().dg_choice_alias_views_by(
            ptr(self.vocab.views), self.k0, self.k1, ptr(self.tab_by), ptr(self.group0[block.start :]),
            ptr(state), block.rows, ptr(self.views[block.start :]),
        )  # fmt: skip


class IndexChoiceJob(Job):
    """Valores não textuais: sorteia o índice (uniforme ou alias) e monta a coluna com ``values[índice]``."""

    def __init__(self, n: int, values: Sequence[Any], tab: np.ndarray | None) -> None:
        self.n = n
        self.k = len(values)
        self.tab = tab
        self.idx = empty(n, np.int32)
        first = values[0]
        if isinstance(first, bool):
            self.values = np.array(values, dtype=np.bool_)
        elif isinstance(first, int):
            self.values = np.array(values, dtype=np.int64)
        else:
            self.values = np.array(values, dtype=np.float64)

    def fill(self, block: Block, state: np.ndarray) -> None:
        out = ptr(self.idx[block.start :])
        if self.tab is None:
            lib().dg_rand_i32(ptr(state), 0, self.k, block.rows, out)
        else:
            lib().dg_alias_idx(self.k, ptr(self.tab), ptr(state), block.rows, out)

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        vals = self.values[self.idx]
        if vals.dtype == np.bool_:
            bits = np.packbits(np.asarray(vals, dtype=np.bool_), bitorder="little")
            return bits_to_series(bits, self.n, name, validity)
        return primitive_to_series(vals, name, validity)


@registry.register
class ChoiceProvider(Provider[ChoiceConfig]):
    kind = "choice"
    config_cls = ChoiceConfig
    positional = "values"
    ns_per_row = 3.6

    def plan(self, run: Run, config: ChoiceConfig, inputs: Mapping[str, Any]) -> Job:
        values = config.values
        tab = cached_alias(config.weights) if config.weights is not None else None
        if isinstance(values[0], str):
            return ViewsChoiceJob(run.n, vocabulary(values), tab)  # type: ignore[arg-type]
        return IndexChoiceJob(run.n, values, tab)
