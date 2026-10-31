"""Entrega os buffers dos kernels ao Polars sem copiar (via Arrow).

Hoje passa pelo pyarrow (``Array.from_buffers`` + ``pl.from_arrow``). A troca pela interface PyCapsule do Arrow, que
dispensaria o pyarrow, está prevista no plano; por isso todo o contato com o pyarrow fica neste módulo.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import polars as pl
import pyarrow as pa

from .views import trim, used_bytes

__all__ = ["bits_to_series", "concat", "numeric_to_series", "views_to_series"]


def views_to_series(views: np.ndarray, data: np.ndarray | None, name: str) -> pl.Series:
    """Views ``(m, 4)`` uint32 (+ buffer de texto) -> ``pl.Series`` String. O buffer é aparado com `trim`."""
    m = len(views)
    if views.dtype != np.uint32 or views.ndim != 2 or views.shape[1] != 4 or not views.flags.c_contiguous:
        raise ValueError("views deve ser um array (m, 4) uint32 contíguo")
    buffers = [None, pa.py_buffer(views)]
    if data is not None:
        buffers.append(pa.py_buffer(trim(data, used_bytes(views))))
    return pl.from_arrow(pa.Array.from_buffers(pa.string_view(), m, buffers)).alias(name)  # type: ignore[union-attr]


def bits_to_series(bits: np.ndarray, m: int, name: str) -> pl.Series:
    """Bits empacotados (LSB primeiro, formato do Arrow) -> ``pl.Series`` Boolean."""
    if bits.nbytes * 8 < m:
        raise ValueError("bits insuficientes para m linhas")
    arr = pa.Array.from_buffers(pa.bool_(), m, [None, pa.py_buffer(bits)])
    return pl.from_arrow(arr).alias(name)  # type: ignore[union-attr]


def numeric_to_series(values: np.ndarray, name: str) -> pl.Series:
    """Array numpy numérico -> ``pl.Series`` (sem cópia para tipos primitivos)."""
    return pl.Series(name, values)


def concat(parts: Sequence[pl.Series], name: str, dtype: pl.DataType) -> pl.Series:
    """Junta os blocos sem reagrupar a memória (``rechunk=False``); ``n=0`` dá uma Series vazia do tipo certo."""
    if not parts:
        return pl.Series(name, [], dtype=dtype)
    if len(parts) == 1:
        return parts[0]
    return pl.concat(parts, rechunk=False)
