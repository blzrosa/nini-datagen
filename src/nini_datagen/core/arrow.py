"""Entrega os buffers dos kernels ao Polars sem copiar (via Arrow).

Hoje passa pelo pyarrow (``Array.from_buffers`` + ``pl.from_arrow``). A troca pela interface PyCapsule do Arrow, que
dispensaria o pyarrow, está prevista no plano; por isso todo o contato com o pyarrow fica neste módulo.

Validade (nulos): bits empacotados no formato do Arrow (1 = valor presente), um bit por linha, LSB primeiro.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import polars as pl
import pyarrow as pa

from .views import trim, used_bytes

__all__ = [
    "apply_validity",
    "arrow_type",
    "bits_to_series",
    "concat",
    "numeric_to_series",
    "primitive_to_series",
    "string_view_buffers",
    "views_to_series",
]

_NUMPY_TO_ARROW = {
    np.dtype(np.int32): pa.int32(),
    np.dtype(np.int64): pa.int64(),
    np.dtype(np.uint32): pa.uint32(),
    np.dtype(np.float32): pa.float32(),
    np.dtype(np.float64): pa.float64(),
}


def arrow_type(kind: str, unit: str | None = None) -> pa.DataType:
    """Tipos Arrow usados pelos geradores: 'int32', 'int64', 'float32', 'float64', 'date', 'datetime'."""
    if kind == "date":
        return pa.date32()
    if kind == "datetime":
        return pa.timestamp(unit or "us")
    return _NUMPY_TO_ARROW[np.dtype(kind)]


def _validity_buffer(validity: np.ndarray | None, m: int) -> pa.Buffer | None:
    if validity is None:
        return None
    if validity.nbytes * 8 < m:
        raise ValueError("bits de validade insuficientes")
    return pa.py_buffer(validity)


def _wrap(arr: pa.Array, name: str) -> pl.Series:
    s = pl.from_arrow(arr)
    assert isinstance(s, pl.Series)
    return s.alias(name)


def views_to_series(
    views: np.ndarray,
    data: np.ndarray | Sequence[np.ndarray] | None,
    name: str,
    validity: np.ndarray | None = None,
    *,
    trim_data: bool = True,
) -> pl.Series:
    """Views ``(m, 4)`` uint32 (+ buffer(s) de texto) -> ``pl.Series`` String.

    ``data``: um buffer, ou uma lista deles (a view longa diz qual, pelo índice de buffer). ``trim_data`` (só com um
    buffer): o kernel escreveu o texto em ordem num buffer com folga, então dá para aparar (`views.trim`). Para views
    que apontam para um vocabulário compartilhado (escolha em lista), passe ``False``.
    """
    m = len(views)
    if views.dtype != np.uint32 or views.ndim != 2 or views.shape[1] != 4 or not views.flags.c_contiguous:
        raise ValueError("views deve ser um array (m, 4) uint32 contíguo")
    buffers = [_validity_buffer(validity, m), pa.py_buffer(views)]
    if isinstance(data, np.ndarray):
        buffers.append(pa.py_buffer(trim(data, used_bytes(views)) if trim_data else data))
    elif data is not None:
        buffers.extend(pa.py_buffer(d) for d in data)
    return _wrap(pa.Array.from_buffers(pa.string_view(), m, buffers), name)


def primitive_to_series(
    values: np.ndarray, name: str, validity: np.ndarray | None = None, typ: pa.DataType | None = None
) -> pl.Series:
    """Array numpy de tipo primitivo -> ``pl.Series``.

    ``typ`` troca o tipo lógico do Arrow (ex.: date32 sobre int32). Sem nulos, vai direto do numpy para o Polars (sem
    cópia, como no MVP): o caminho pelo pyarrow, medido no Windows, custava ~0,1 ns por byte a mais, proporcional ao
    tamanho da coluna (o Polars copiava o buffer importado). Com nulos, o pyarrow junta o buffer de validade.
    """
    if values.ndim != 1 or not values.flags.c_contiguous:
        raise ValueError("values deve ser 1-D e contíguo")
    if validity is None:
        s = pl.Series(name, values)
        if typ is None:
            return s
        if pa.types.is_date32(typ):
            return s.cast(pl.Date)
        if pa.types.is_timestamp(typ):
            return s.cast(pl.Datetime(typ.unit))
        raise ValueError(f"tipo lógico não suportado: {typ}")
    typ = typ if typ is not None else _NUMPY_TO_ARROW[values.dtype]
    m = len(values)
    return _wrap(pa.Array.from_buffers(typ, m, [_validity_buffer(validity, m), pa.py_buffer(values)]), name)


def numeric_to_series(values: np.ndarray, name: str) -> pl.Series:
    """Array numpy numérico -> ``pl.Series`` (sem cópia para tipos primitivos)."""
    return pl.Series(name, values)


def bits_to_series(bits: np.ndarray, m: int, name: str, validity: np.ndarray | None = None) -> pl.Series:
    """Bits empacotados (LSB primeiro, formato do Arrow) -> ``pl.Series`` Boolean."""
    if bits.nbytes * 8 < m:
        raise ValueError("bits insuficientes para m linhas")
    return _wrap(pa.Array.from_buffers(pa.bool_(), m, [_validity_buffer(validity, m), pa.py_buffer(bits)]), name)


def string_view_buffers(s: pl.Series) -> tuple[np.ndarray, np.ndarray | None, int, object] | None:
    """As views ``(m, 4)`` uint32 e os bits de validade de uma Series String, sem copiar, para um kernel ler direto.

    Devolve ``(views, validade ou None, deslocamento em bits da validade, dono dos buffers)`` — guarde o dono enquanto
    usar as views — ou None se o Polars não entregar a coluna como ``string_view`` de um pedaço só (aí o chamador usa
    o caminho em Polars).
    """
    try:
        arr = s.to_arrow(compat_level=pl.CompatLevel.newest())
    except Exception:  # Polars antigo ou tipo sem exportação: cai no caminho em Polars
        return None
    if isinstance(arr, pa.ChunkedArray):
        if arr.num_chunks != 1:
            return None
        arr = arr.chunk(0)
    if arr.type != pa.string_view():
        return None
    validity, views = arr.buffers()[:2]
    if views is None:
        return None
    off, m = arr.offset, len(arr)
    v = np.frombuffer(views, dtype=np.uint32).reshape(-1, 4)[off : off + m]
    bits = np.frombuffer(validity, dtype=np.uint8) if validity is not None else None
    return v, bits, off, arr


def apply_validity(s: pl.Series, validity: np.ndarray | None) -> pl.Series:
    """Anula as linhas cujo bit de validade é 0 (para geradores compostos, que não montam os buffers sozinhos)."""
    if validity is None:
        return s
    keep = bits_to_series(validity, len(s), "_keep")
    return pl.select(pl.when(pl.lit(keep)).then(pl.lit(s))).to_series().alias(s.name)


def concat(parts: Sequence[pl.Series], name: str, dtype: pl.DataType) -> pl.Series:
    """Junta os blocos sem reagrupar a memória (``rechunk=False``); ``n=0`` dá uma Series vazia do tipo certo."""
    if not parts:
        return pl.Series(name, [], dtype=dtype)
    if len(parts) == 1:
        return parts[0]
    return pl.concat(parts, rechunk=False)
