"""Estruturas pré-montadas que os kernels leem: tabela alias (sorteio ponderado) e vocabulário (strings como views).

São construídas uma vez por conjunto de dados (cache no locale ou no provider) e só lidas depois, por várias threads.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .._native import lib, ptr
from .views import INLINE_MAX

__all__ = ["ViewTable", "Vocabulary", "alias_table", "check_weights"]


def check_weights(weights: Sequence[float] | np.ndarray, k: int | None = None) -> np.ndarray:
    """Pesos como float64 contíguo; exige 1-D, finitos, não negativos e soma > 0 (e `k` valores, se dado)."""
    w = np.ascontiguousarray(weights, dtype=np.float64)
    if w.ndim != 1 or len(w) == 0:
        raise ValueError("weights deve ser uma lista não vazia")
    if k is not None and len(w) != k:
        raise ValueError(f"weights tem {len(w)} valores, mas são {k} opções")
    if not np.isfinite(w).all() or (w < 0).any():
        raise ValueError("weights deve ter só valores finitos e >= 0")
    if w.sum() <= 0:
        raise ValueError("a soma de weights deve ser > 0")
    if len(w) >= 2**32:
        raise ValueError("opções demais (máximo 2^32 - 1)")
    return w


def alias_table(weights: Sequence[float] | np.ndarray) -> np.ndarray:
    """Tabela alias de Vose empacotada para o C++: ``uint64 = limiar (32 bits baixos) | alias << 32``.

    Sorteio O(1) por linha com probabilidade proporcional a ``weights``; peso zero nunca sai.
    """
    w = check_weights(weights)
    tab = np.empty(len(w), np.uint64)
    lib().dg_alias_build(ptr(w), len(w), ptr(tab))
    return tab


@dataclass(frozen=True, eq=False)
class Vocabulary:
    """Strings pré-montadas como views do Arrow (``views`` (k, 4) uint32) + buffer com o texto das longas (``data``).

    O kernel de escolha copia a view (16 bytes) da opção sorteada; todas as linhas apontam para o mesmo ``data``, então
    a coluna gerada não copia texto nenhum.
    """

    strings: tuple[str, ...]
    views: np.ndarray
    data: np.ndarray | None

    def __len__(self) -> int:
        return len(self.strings)

    @classmethod
    def from_strings(cls, strings: Sequence[str]) -> Vocabulary:
        strings = tuple(strings)
        k = len(strings)
        if k == 0:
            raise ValueError("vocabulário vazio")
        views = np.zeros((k, 4), np.uint32)
        raw = views.view(np.uint8).reshape(k, 16)
        chunks: list[bytes] = []
        offset = 0
        for i, s in enumerate(strings):
            if not isinstance(s, str):
                raise TypeError(f"esperava texto, veio {type(s).__name__} ({s!r})")
            b = s.encode("utf-8")
            views[i, 0] = len(b)
            if len(b) <= INLINE_MAX:
                raw[i, 4 : 4 + len(b)] = np.frombuffer(b, np.uint8)
            else:
                if offset + len(b) >= 2**31:
                    raise ValueError("texto demais no vocabulário (limite de 2 GiB)")
                raw[i, 4:8] = np.frombuffer(b[:4], np.uint8)
                views[i, 2] = 0  # índice do buffer de dados
                views[i, 3] = offset
                chunks.append(b)
                offset += len(b)
        data = np.frombuffer(b"".join(chunks), np.uint8).copy() if chunks else None
        views.setflags(write=False)
        if data is not None:
            data.setflags(write=False)
        return cls(strings, views, data)

    def slice(self, start: int, stop: int) -> Vocabulary:
        """Sub-vocabulário (as views continuam apontando para o mesmo ``data``)."""
        return Vocabulary(self.strings[start:stop], self.views[start:stop], self.data)


@dataclass(frozen=True, eq=False)
class ViewTable:
    """Strings como views (``views`` (k, 4) uint32) + todos os buffers de texto a que elas apontam (``datas``, na ordem
    do índice de buffer da view). Como `Vocabulary`, mas sem a lista de strings em Python: serve para tabelas grandes
    (milhões de nomes de rua) vindas direto de uma Series do Polars, sem copiar o texto. ``owner`` mantém vivos os
    buffers originais."""

    views: np.ndarray
    datas: tuple[np.ndarray, ...]
    owner: object = None

    def __len__(self) -> int:
        return len(self.views)

    @classmethod
    def from_strings(cls, strings: Sequence[str]) -> ViewTable:
        v = Vocabulary.from_strings(strings)
        return cls(v.views, () if v.data is None else (v.data,), v)

    @classmethod
    def from_series(cls, s: Any) -> ViewTable:
        """Series String sem nulos -> views e buffers dela mesma (sem copiar); se o Polars não entregar como
        ``string_view`` de um pedaço só, monta pelas strings (lento, mas correto)."""
        from .arrow import string_view_buffers  # noqa: PLC0415 (arrow importa polars/pyarrow)

        if s.null_count():
            raise ValueError("a tabela de nomes não pode ter nulos")
        got = string_view_buffers(s.rechunk())
        if got is None:
            return cls.from_strings(s.to_list())
        views, _, _, arr = got
        datas = tuple(np.frombuffer(b, np.uint8) for b in arr.buffers()[2:] if b is not None)  # type: ignore[attr-defined]
        views = np.ascontiguousarray(views)
        views.setflags(write=False)
        return cls(views, datas, arr)
