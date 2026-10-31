"""Divisão em blocos fixos de linhas e execução paralela.

O tamanho do bloco é fixo (``BLOCK_ROWS``) e faz parte do contrato de reprodutibilidade: mudar esse número muda os dados
gerados para a mesma semente. Por isso ele não é configurável.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TypeVar

__all__ = ["BLOCK_ROWS", "THREADS_ENV", "Block", "map_blocks", "resolve_threads", "split"]

BLOCK_ROWS = 65_536
THREADS_ENV = "NINI_DATAGEN_THREADS"

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Block:
    index: int  # índice do bloco no fluxo (define o estado do gerador)
    start: int  # primeira linha do bloco
    rows: int  # quantidade de linhas (BLOCK_ROWS, exceto no último)


def split(n: int) -> list[Block]:
    """Blocos que cobrem as linhas ``0 .. n-1``."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(f"n deve ser um inteiro, não {type(n).__name__}")
    if n < 0:
        raise ValueError("n deve ser >= 0")
    return [Block(i, s, min(BLOCK_ROWS, n - s)) for i, s in enumerate(range(0, n, BLOCK_ROWS))]


def resolve_threads(threads: int | None = None) -> int:
    """Número de threads: o pedido, senão ``NINI_DATAGEN_THREADS``, senão o número de CPUs disponíveis."""
    if threads is None:
        env = os.environ.get(THREADS_ENV)
        if env:
            try:
                threads = int(env)
            except ValueError:
                raise ValueError(f"{THREADS_ENV}={env!r} não é um inteiro") from None
        else:
            threads = _cpu_count()
    if isinstance(threads, bool) or not isinstance(threads, int):
        raise TypeError("threads deve ser um inteiro")
    if threads < 1:
        raise ValueError("threads deve ser >= 1")
    return threads


def _cpu_count() -> int:
    if hasattr(os, "process_cpu_count"):  # Python 3.13+: respeita afinidade/cgroups
        return os.process_cpu_count() or 1  # type: ignore[attr-defined]
    if hasattr(os, "sched_getaffinity"):
        return len(os.sched_getaffinity(0)) or 1
    return os.cpu_count() or 1


def map_blocks(fn: Callable[[Block], T], blocks: Sequence[Block], threads: int | None = None) -> list[T]:
    """Aplica ``fn`` a cada bloco e devolve os resultados na ordem dos blocos (paralelo quando vale a pena)."""
    workers = min(resolve_threads(threads), len(blocks))
    if workers <= 1:
        return [fn(b) for b in blocks]
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="nini-datagen") as pool:
        return list(pool.map(fn, blocks))
