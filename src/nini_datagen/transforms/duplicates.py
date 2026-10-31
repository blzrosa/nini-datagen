"""Duplicatas com gabarito: cópias (exatas ou sujas) de linhas sorteadas, para testar deduplicação e fuzzy matching."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import polars as pl

from ..config.dirty import DirtyConfig
from ..core.blocks import split
from .dirty import RowStreams, apply_dirty

__all__ = ["add_duplicates"]


def add_duplicates(
    df: pl.DataFrame,
    p: float = 0.02,
    *,
    dirty: Mapping[str, DirtyConfig | Mapping[str, Any]] | None = None,
    shuffle: bool = True,
    seed: int = 0,
    row_id: str = "row_id",
    dup_of: str = "dup_of",
) -> pl.DataFrame:
    """Acrescenta ``round(p * n)`` linhas que copiam linhas sorteadas (com reposição) de ``df``.

    * ``dirty``: defeitos por coluna aplicados só nas cópias, como em `DirtyConfig`
      (``{"nome": {"typo": 0.3}, "cpf": {"unmask": 0.5}}``);
    * ``row_id`` (0, 1, ...) numera todas as linhas e ``dup_of`` traz o ``row_id`` da original nas cópias (nulo nas
      originais): os pares ``(row_id, dup_of)`` são o gabarito dos duplicados;
    * ``shuffle``: mistura as linhas (senão as cópias vão no fim).

    O resultado depende só de (``df``, ``p``, ``dirty``, ``seed``).
    """
    if not 0.0 <= p <= 10.0:
        raise ValueError("p deve estar entre 0 e 10 (fração de linhas a mais)")
    for c in (row_id, dup_of):
        if c in df.columns:
            raise ValueError(f"a coluna {c!r} já existe; escolha outro nome com row_id=/dup_of=")
    specs = {c: v if isinstance(v, DirtyConfig) else DirtyConfig.model_validate(v) for c, v in (dirty or {}).items()}
    missing = sorted(set(specs) - set(df.columns))
    if missing:
        raise ValueError(f"dirty cita colunas que não existem: {', '.join(missing)}")
    n = df.height
    k = round(p * n) if n else 0
    base = df.with_columns(
        pl.Series(row_id, np.arange(n, dtype=np.int64)), pl.Series(dup_of, [None] * n, dtype=pl.Int64)
    )
    if k == 0:
        return base
    src = RowStreams(seed, "duplicates", split(k), 0, k).integers(":source", n)
    copies = df[src]
    for col, cfg in specs.items():
        rows = RowStreams(seed, f"duplicates.{col}", split(k), 0, k)
        copies = copies.with_columns(apply_dirty(copies[col], cfg, rows).alias(col))
    copies = copies.with_columns(
        pl.Series(row_id, np.arange(n, n + k, dtype=np.int64)), pl.Series(dup_of, src.astype(np.int64))
    )
    out = pl.concat([base, copies], how="vertical")
    if shuffle:
        total = n + k
        keys = RowStreams(seed, "duplicates", split(total), 0, total).integers(":order")
        out = out[np.argsort(keys, kind="stable")]
    return out
