"""Entrega os buffers dos kernels ao Polars sem copiar, pela interface C do Arrow (`arrow_c`), sem o pyarrow.

Até a 0.2.1 passava pelo pyarrow (``Array.from_buffers`` + ``pl.from_arrow``); desde a 0.3.0 os buffers vão direto ao
Polars por PyCapsule (``__arrow_c_array__``), e as colunas de texto que o C++ lê vêm do ``__arrow_c_stream__`` da
Series. Todo o contato com o formato Arrow fica neste módulo e em `arrow_c`.

Validade (nulos): bits empacotados no formato do Arrow (1 = valor presente), um bit por linha, LSB primeiro.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import polars as pl

from .._native import lib, ptr
from .arrow_c import Imported, export_array, import_series
from .views import trim, used_bytes

__all__ = [
    "ArrowType",
    "StringViews",
    "apply_validity",
    "arrow_type",
    "bits_to_series",
    "concat",
    "numeric_to_series",
    "primitive_to_series",
    "string_view_buffers",
    "views_to_series",
]


@dataclass(frozen=True)
class ArrowType:
    """Tipo lógico de uma coluna primitiva: formato da interface C do Arrow e o tipo do Polars."""

    format: bytes
    dtype: pl.DataType


_NUMPY_FORMATS = {
    np.dtype(np.int32): b"i",
    np.dtype(np.int64): b"l",
    np.dtype(np.uint32): b"I",
    np.dtype(np.uint8): b"C",
    np.dtype(np.float32): b"f",
    np.dtype(np.float64): b"g",
}
_TIME_UNITS = {"ms": b"m", "us": b"u", "ns": b"n"}


def arrow_type(kind: str, unit: str | None = None) -> ArrowType:
    """Tipos lógicos usados pelos geradores: 'date' (Date sobre int32) e 'datetime' (Datetime sobre int64)."""
    if kind == "date":
        return ArrowType(b"tdD", pl.Date())
    if kind == "datetime":
        u = unit or "us"
        if u not in _TIME_UNITS:
            raise ValueError(f"unidade de tempo não suportada: {u}")
        return ArrowType(b"ts" + _TIME_UNITS[u] + b":", pl.Datetime(u))  # type: ignore[arg-type]
    raise ValueError(f"tipo lógico não suportado: {kind}")


def _check_validity(validity: np.ndarray | None, m: int) -> np.ndarray | None:
    if validity is None:
        return None
    if validity.nbytes * 8 < m:
        raise ValueError("bits de validade insuficientes")
    if not validity.flags.c_contiguous:
        validity = np.ascontiguousarray(validity)
    return validity


def _null_count(validity: np.ndarray | None, m: int) -> int:
    return 0 if validity is None else int(lib().dg_count_unset(ptr(validity), m))


def _series(fmt: bytes, m: int, buffers: list[np.ndarray | None], validity: np.ndarray | None, name: str) -> pl.Series:
    exported = export_array(fmt, m, [validity, *buffers], _null_count(validity, m))
    return pl.Series(values=exported).alias(name)  # pyright: ignore[reportArgumentType]


_NO_SIZES = np.zeros(1, np.int64)  # buffer de tamanhos de uma string_view sem buffers de texto (não pode ser nulo)


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
    if isinstance(data, np.ndarray):
        datas = [trim(data, used_bytes(views)) if trim_data else data]
    else:
        datas = list(data) if data is not None else []
    datas = [d if d.flags.c_contiguous else np.ascontiguousarray(d) for d in datas]
    # string_view na interface C: validade, views, os buffers de texto e, por último, o tamanho (int64) de cada um
    sizes = np.array([d.nbytes for d in datas], np.int64) if datas else _NO_SIZES
    validity = _check_validity(validity, m)
    return _series(b"vu", m, [views, *datas, sizes], validity, name)


def primitive_to_series(
    values: np.ndarray, name: str, validity: np.ndarray | None = None, typ: ArrowType | None = None
) -> pl.Series:
    """Array numpy de tipo primitivo -> ``pl.Series``.

    ``typ`` troca o tipo lógico (ex.: Date sobre int32). Sem nulos, vai direto do numpy para o Polars (sem cópia, como
    no MVP); com nulos, pela interface C do Arrow, com o buffer de validade junto.
    """
    if values.ndim != 1 or not values.flags.c_contiguous:
        raise ValueError("values deve ser 1-D e contíguo")
    if validity is None:
        s = pl.Series(name, values)
        return s if typ is None else s.cast(typ.dtype)
    fmt = typ.format if typ is not None else _NUMPY_FORMATS.get(values.dtype)
    if fmt is None:
        raise ValueError(f"tipo numpy não suportado: {values.dtype}")
    m = len(values)
    return _series(fmt, m, [values], _check_validity(validity, m), name)


def numeric_to_series(values: np.ndarray, name: str) -> pl.Series:
    """Array numpy numérico -> ``pl.Series`` (sem cópia para tipos primitivos)."""
    return pl.Series(name, values)


def bits_to_series(bits: np.ndarray, m: int, name: str, validity: np.ndarray | None = None) -> pl.Series:
    """Bits empacotados (LSB primeiro, formato do Arrow) -> ``pl.Series`` Boolean."""
    if bits.nbytes * 8 < m:
        raise ValueError("bits insuficientes para m linhas")
    if not bits.flags.c_contiguous:
        bits = np.ascontiguousarray(bits)
    return _series(b"b", m, [bits], _check_validity(validity, m), name)


@dataclass(frozen=True)
class StringViews:
    """Os buffers de uma Series String (string_view), sem copiar. Guarde o objeto enquanto usar os arrays: ele é o
    dono da memória (o Polars só a libera quando ele deixa de existir)."""

    views: np.ndarray  # (m, 4) uint32, já a partir do deslocamento
    validity: np.ndarray | None  # bits (uint8) a partir do byte 0: use ``bit_offset``
    bit_offset: int
    datas: tuple[np.ndarray, ...]  # os buffers de texto, na ordem do índice de buffer das views
    owner: Imported


def _from_address(addr: int, nbytes: int, dtype: type, owner: Imported) -> np.ndarray:
    """Array NumPy sobre memória do Polars; o array segura ``owner`` (o dono dela), como faria um buffer do pyarrow."""
    import ctypes  # noqa: PLC0415

    if nbytes == 0:
        return np.empty(0, dtype)
    raw = (ctypes.c_uint8 * nbytes).from_address(addr)
    raw.owner = owner  # type: ignore[attr-defined]  # o ctypes aceita atributos: liga a vida da memória ao array
    return np.frombuffer(memoryview(raw).cast("B"), dtype)  # a memoryview segura `raw`, que segura o dono


def string_view_buffers(s: pl.Series) -> StringViews | None:
    """Os buffers de uma Series String, sem copiar, para um kernel ler direto; None se o Polars não entregar a coluna
    como ``string_view`` de um pedaço só (aí o chamador usa o caminho em Polars)."""
    imp = import_series(s)
    if imp is None or imp.format != b"vu":
        return None
    arr = imp.array
    off, m, nb = int(arr.offset), int(arr.length), int(arr.n_buffers)
    views_addr = imp.buffer(1)
    if views_addr is None or nb < 3:
        return None
    views = _from_address(views_addr, (off + m) * 16, np.uint32, imp).reshape(-1, 4)[off : off + m]
    vaddr = imp.buffer(0)
    validity = _from_address(vaddr, (off + m + 7) // 8, np.uint8, imp) if vaddr is not None else None
    k = nb - 3  # buffers de texto; o último buffer é o dos tamanhos
    sizes_addr = imp.buffer(nb - 1)
    sizes = _from_address(sizes_addr, 8 * k, np.int64, imp) if (k and sizes_addr is not None) else np.zeros(0, np.int64)
    datas = []
    for j in range(k):
        addr = imp.buffer(2 + j)
        datas.append(_from_address(addr, int(sizes[j]), np.uint8, imp) if addr is not None else np.empty(0, np.uint8))
    return StringViews(views, validity, off, tuple(datas), imp)


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
