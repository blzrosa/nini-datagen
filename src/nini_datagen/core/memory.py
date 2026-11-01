"""Memória dos buffers grandes (colunas, textos): vem do pool do C++ (`cpp/memory.cpp`), que reaproveita as páginas.

Com ``np.empty`` (o malloc do sistema), cada tabela grande pede memória nova ao sistema operacional, que entrega as
páginas uma a uma na primeira escrita, e devolve tudo quando a tabela é liberada. Medido no Windows (tabela de 20
colunas, 228 MB por milhão de linhas): a primeira escrita custava ~54 ns/linha com 1 thread contra ~15 da segunda, e
liberar, ~27 ns/linha. O pool guarda a memória liberada (até ``pool_limit``, 1 GiB por padrão) para a próxima
alocação: gerar de novo (outra tabela, o próximo lote do `scan` ou do `write_parquet_dataset`) não paga nenhum dos
dois custos. Na 0.2.1 o pool era o do pyarrow; o próprio deixa o pacote dispensar o pyarrow.

O array devolvido é um array NumPy comum sobre o bloco do pool; o bloco volta ao pool quando o array (e tudo que o
segura: fatias, a Series do Polars feita dele) deixa de existir. Buffers pequenos continuam com ``np.empty``.

``NINI_DATAGEN_POOL``: ``0`` desliga o pool (tudo com ``np.empty``); ``arrow`` usa o pool do pyarrow, como na 0.2.1
(só para comparar; precisa do pyarrow instalado, que o pacote não exige).
"""

from __future__ import annotations

import ctypes
import importlib
import math
import os
import weakref
from typing import Any

import numpy as np

from .._native import lib

__all__ = ["POOL_ENV", "POOL_MIN_BYTES", "empty", "pool_limit", "pool_stats", "release_memory"]

POOL_ENV = "NINI_DATAGEN_POOL"
POOL_MIN_BYTES = 1 << 20  # abaixo disso o malloc do sistema já reaproveita a memória
_GRAIN = 1 << 16  # o pool arredonda para múltiplos de 64 KiB
_Chunk = ctypes.c_uint8 * _GRAIN


def _native_block(nbytes: int) -> ctypes.Array[Any]:
    """Bloco do pool como array do ctypes, que devolve o bloco ao pool quando é coletado."""
    dg = lib()
    addr = dg.dg_pool_alloc(nbytes)
    if not addr:
        raise MemoryError(f"sem memória para {nbytes:,} bytes")
    # array de pedaços de 64 KiB: poucos tipos do ctypes distintos (o ctypes guarda um tipo por tamanho de array)
    block = (_Chunk * -(-nbytes // _GRAIN)).from_address(addr)
    weakref.finalize(block, dg.dg_pool_free, addr)
    return block


def _arrow_block(nbytes: int) -> Any:
    try:
        pa = importlib.import_module("pyarrow")  # opcional: só para comparar (o pacote não depende dele)
    except ImportError as e:
        raise RuntimeError(f"{POOL_ENV}=arrow precisa do pyarrow (uv sync --group arrow)") from e
    return pa.allocate_buffer(nbytes)


def empty(shape: int | tuple[int, ...], dtype: Any) -> np.ndarray:
    """Como ``np.empty(shape, dtype)`` (C-contíguo, conteúdo indefinido), com a memória do pool."""
    dt = np.dtype(dtype)
    dims = (shape,) if isinstance(shape, int) else tuple(shape)
    count = math.prod(dims)
    nbytes = count * dt.itemsize
    mode = os.environ.get(POOL_ENV, "1")
    if nbytes < POOL_MIN_BYTES or mode == "0":
        return np.empty(dims, dt)
    if mode == "arrow":
        arr = np.frombuffer(_arrow_block(nbytes), dt, count).reshape(dims)
    else:  # a memoryview segura o bloco; o array segura a memoryview
        arr = np.frombuffer(memoryview(_native_block(nbytes)).cast("B"), dt, count).reshape(dims)
    if not arr.flags.writeable:  # pragma: no cover (os dois tipos de bloco são graváveis)
        return np.empty(dims, dt)
    return arr


def pool_stats() -> dict[str, int]:
    """Bytes em uso e guardados no pool, e quantas alocações ele atendeu (``hits``) ou pediu ao sistema."""
    out = (ctypes.c_int64 * 4)()
    lib().dg_pool_stats(out)
    return {"in_use": out[0], "cached": out[1], "hits": out[2], "misses": out[3]}


def pool_limit(nbytes: int | None = None) -> int:
    """Limite de bytes guardados no pool depois de liberados (padrão 1 GiB); ``None`` só consulta; 0 desliga."""
    return int(lib().dg_pool_limit(-1 if nbytes is None else max(0, int(nbytes))))


def release_memory() -> None:
    """Devolve ao sistema operacional a memória guardada no pool (as tabelas ainda em uso não são afetadas)."""
    lib().dg_pool_trim()
