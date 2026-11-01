"""Memória dos buffers grandes (colunas, textos): vem do pool de memória do Arrow, que reaproveita as páginas.

Com ``np.empty`` (o malloc do sistema), cada tabela grande pede memória nova ao sistema operacional, que entrega as
páginas uma a uma na primeira escrita, e devolve tudo quando a tabela é liberada. Medido no Windows (tabela de 20
colunas, 228 MB por milhão de linhas): a primeira escrita custava ~54 ns/linha com 1 thread contra ~15 da segunda, e
liberar, ~27 ns/linha. O pool do Arrow (mimalloc no Windows e no macOS, jemalloc no Linux) guarda a memória liberada
para a próxima alocação: gerar de novo (outra tabela, o próximo lote do `scan` ou do `write_parquet_dataset`) não paga
nenhum dos dois custos.

O array devolvido é um array NumPy comum sobre o buffer do Arrow; o buffer vive enquanto o array (ou a Series do
Polars feita dele) existir. Buffers pequenos continuam com ``np.empty``. ``NINI_DATAGEN_POOL=0`` desliga o pool (tudo
com ``np.empty``), para comparar ou se o pool atrapalhar em alguma máquina.
"""

from __future__ import annotations

import math
import os
from typing import Any

import numpy as np

__all__ = ["POOL_ENV", "POOL_MIN_BYTES", "empty"]

POOL_ENV = "NINI_DATAGEN_POOL"

POOL_MIN_BYTES = 1 << 20  # abaixo disso o malloc do sistema já reaproveita a memória


def _allocate(nbytes: int) -> Any:
    try:
        import pyarrow as pa  # noqa: PLC0415
    except ImportError:  # pragma: no cover (o pyarrow é dependência; isto só protege ferramentas sem ele)
        return None
    return pa.allocate_buffer(nbytes)


def empty(shape: int | tuple[int, ...], dtype: Any) -> np.ndarray:
    """Como ``np.empty(shape, dtype)`` (C-contíguo, conteúdo indefinido), com a memória do pool do Arrow."""
    dt = np.dtype(dtype)
    dims = (shape,) if isinstance(shape, int) else tuple(shape)
    count = math.prod(dims)
    nbytes = count * dt.itemsize
    if nbytes < POOL_MIN_BYTES or os.environ.get(POOL_ENV, "1") == "0":
        return np.empty(dims, dt)
    buf = _allocate(nbytes)
    if buf is None:
        return np.empty(dims, dt)
    arr = np.frombuffer(buf, dt, count).reshape(dims)
    if not arr.flags.writeable:  # pragma: no cover (buffers do allocate_buffer são graváveis)
        return np.empty(dims, dt)
    return arr
