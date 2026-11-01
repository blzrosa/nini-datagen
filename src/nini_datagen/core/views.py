"""Buffers que os kernels escrevem: views de 16 bytes do Arrow ``string_view`` + buffer de texto.

Layout de cada view (4 x uint32, little-endian):
* ``len <= 12``: ``[len, bytes 0..3, bytes 4..7, bytes 8..11]`` (texto inteiro na própria view);
* ``len > 12``: ``[len, prefixo (bytes 0..3), índice do buffer, deslocamento no buffer]``.

Este módulo só usa numpy (sem Polars; o pyarrow só para alocar buffers grandes, em `memory`).
"""

from __future__ import annotations

import numpy as np

from .memory import empty

__all__ = ["INLINE_MAX", "decode", "empty_views", "trim", "used_bytes"]

INLINE_MAX = 12


def empty_views(m: int) -> np.ndarray:
    """Array ``(m, 4)`` de uint32 para os kernels preencherem."""
    return np.empty((m, 4), np.uint32)


def used_bytes(views: np.ndarray) -> int:
    """Bytes do buffer de texto realmente usados: fim da última string fora da view (os kernels escrevem em ordem)."""
    big = np.flatnonzero(views[:, 0] > INLINE_MAX)
    if not len(big):
        return 0
    last = big[-1]
    return int(views[last, 3]) + int(views[last, 0])


def trim(data: np.ndarray, used: int) -> np.ndarray:
    """O buffer de texto é alocado com folga (limite superior). Uma fatia ``data[:used]`` manteria o buffer inteiro
    vivo junto com a Series; quando sobra mais da metade, copia só o trecho usado (um memcpy dos bytes úteis)."""
    if used > data.nbytes:
        raise ValueError(f"used={used} maior que o buffer ({data.nbytes} bytes)")
    if data.nbytes > 2 * used + 65_536:
        out = empty(used, np.uint8)
        out[:] = data[:used]
        return out
    return data[:used]


def decode(views: np.ndarray, data: np.ndarray | None = None, buffers: list[np.ndarray] | None = None) -> list[bytes]:
    """Lê as strings de volta (lento, em Python): para testes e depuração, não para o caminho de produção."""
    if buffers is None:
        buffers = [] if data is None else [np.ascontiguousarray(data).view(np.uint8).ravel()]
    raw = np.ascontiguousarray(views, dtype=np.uint32).view(np.uint8).reshape(-1, 16)
    out: list[bytes] = []
    for i in range(len(raw)):
        n, buf, off = int(views[i, 0]), int(views[i, 2]), int(views[i, 3])
        if n <= INLINE_MAX:
            out.append(raw[i, 4 : 4 + n].tobytes())
        else:
            s = buffers[buf][off : off + n].tobytes()
            if s[:4] != raw[i, 4:8].tobytes():
                raise ValueError(f"linha {i}: prefixo da view não bate com o texto no buffer")
            out.append(s)
    return out
