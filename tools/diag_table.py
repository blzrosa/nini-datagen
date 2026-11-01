"""diag_table.py -- por que a tabela escala só ~3x com 16 threads (diagnóstico para a 0.2.1).

    uv run python tools/diag_table.py              # 1 milhão de linhas da tabela de 20 colunas
    uv run python tools/diag_table.py -n 2000000

Em ns por linha, melhor de 3:

1. as etapas do `table` medidas na parede (não somadas entre threads): planejar (`prepare`), preencher (`fill`),
   montar as Series (`finish`) e o resto (expressões, montar o DataFrame), e quanto custa liberar a tabela (`del`);
2. a memória sozinha, com o mesmo tamanho da tabela em 40 buffers (como as colunas): escrever pela primeira vez
   (o sistema entrega as páginas uma a uma), escrever de novo (páginas já entregues) e liberar; com o malloc do
   sistema (NumPy) e com o pool de memória do pyarrow (que pode guardar a memória para a próxima vez);
3. quanto custa criar o pool de threads (o `table` cria 3 por nível de dependência).

Se a primeira escrita e a liberação custam perto do que sobra da tabela, o limite é o sistema operacional
entregando e tomando de volta a memória, não o código.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))

import nini_datagen as dg
from bench import TABLE_20
from nini_datagen.schema import plan

PIECES = 40


def best(fn: Callable[[], Any], repeats: int = 3) -> float:
    t = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        t = min(t, time.perf_counter() - t0)
    return t


def stages(n: int, threads: int) -> int:
    """Etapas do table na parede; devolve o tamanho da tabela em bytes."""
    g = dg.DataGen(seed=1, threads=threads)
    g.table(min(n, 100_000), TABLE_20)
    wall: dict[str, float] = {}
    orig_map, orig_fill = plan._map, plan._fill

    def timed_map(fn: Any, items: Any, th: Any) -> Any:
        t0 = time.perf_counter()
        try:
            return orig_map(fn, items, th)
        finally:
            key = "finish" if getattr(fn, "__name__", "") == "finish" else "prepare"
            wall[key] = wall.get(key, 0.0) + time.perf_counter() - t0

    def timed_fill(*a: Any) -> Any:
        t0 = time.perf_counter()
        try:
            return orig_fill(*a)
        finally:
            wall["fill"] = wall.get("fill", 0.0) + time.perf_counter() - t0

    best_parts: dict[str, float] = {}
    best_total = float("inf")
    size = 0
    mod: Any = plan  # troca as funções do módulo (o pyright não aceita reatribuir funções declaradas)
    mod._map, mod._fill = timed_map, timed_fill
    try:
        for _ in range(3):
            wall.clear()
            t0 = time.perf_counter()
            df = g.table(n, TABLE_20)
            t1 = time.perf_counter()
            size = int(df.estimated_size())
            t2 = time.perf_counter()
            del df
            t3 = time.perf_counter()
            total = t1 - t0
            if total < best_total:
                best_total = total
                best_parts = dict(wall)
                best_parts["resto"] = total - sum(wall.values())
                best_parts["del"] = t3 - t2
    finally:
        mod._map, mod._fill = orig_map, orig_fill
    parts = "  ".join(f"{k} {v / n * 1e9:6.1f}" for k, v in best_parts.items())
    print(f"threads={threads:<3} table {best_total / n * 1e9:7.1f}   [{parts}]")
    return size


def touch(arrays: list[np.ndarray], threads: int) -> None:
    def one(a: np.ndarray) -> None:
        np.copyto(a, 1)  # o NumPy solta o GIL em cópias grandes

    if threads <= 1:
        for a in arrays:
            one(a)
    else:
        with ThreadPoolExecutor(threads) as pool:
            list(pool.map(one, arrays))


def memory(size: int, n: int, threads: int) -> None:
    piece = size // PIECES
    pool = pa.default_memory_pool()

    def numpy_bufs() -> list[np.ndarray]:
        return [np.empty(piece, np.uint8) for _ in range(PIECES)]

    def arrow_bufs() -> tuple[list[Any], list[np.ndarray]]:
        bufs = [pa.allocate_buffer(piece, memory_pool=pool) for _ in range(PIECES)]
        return bufs, [np.frombuffer(b, np.uint8) for b in bufs]

    def native_bufs() -> tuple[None, list[np.ndarray]]:
        from nini_datagen.core.memory import empty  # noqa: PLC0415

        return None, [empty(piece, np.uint8) for _ in range(PIECES)]

    options = (
        ("NumPy (malloc)", None),
        (f"pyarrow ({pool.backend_name})", arrow_bufs),
        ("pool do nini (C++)", native_bufs),
    )
    for label, make in options:
        first = second = free = float("inf")
        for _ in range(3):
            if make is None:
                arrays = numpy_bufs()
                keep: Any = None
            else:
                keep, arrays = make()
            t0 = time.perf_counter()
            touch(arrays, threads)
            t1 = time.perf_counter()
            touch(arrays, threads)
            t2 = time.perf_counter()
            del arrays, keep
            t3 = time.perf_counter()
            first, second, free = min(first, t1 - t0), min(second, t2 - t1), min(free, t3 - t2)
        print(
            f"threads={threads:<3} {label:<22} 1ª escrita {first / n * 1e9:6.1f}   2ª escrita {second / n * 1e9:6.1f}"
            f"   liberar {free / n * 1e9:6.1f}"
        )


def pools(n: int, threads: int) -> None:
    def create() -> None:
        with ThreadPoolExecutor(max_workers=threads) as pool:
            list(pool.map(lambda x: x, range(threads)))

    t = best(create, 10)
    print(f"criar e fechar um pool de {threads} threads: {t * 1e3:.2f} ms ({t / n * 1e9:.2f} ns/linha por pool)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=1_000_000)
    args = ap.parse_args()
    n, cpus = args.n, os.cpu_count() or 1
    print(f"== etapas do table, {n:,} linhas (ns/linha, parede) ==")
    size = 0
    for threads in (1, cpus):
        size = stages(n, threads)
    print(f"\n== memória do tamanho da tabela ({size / 2**20:.0f} MB em {PIECES} buffers; ns por linha da tabela) ==")
    for threads in (1, cpus):
        memory(size, n, threads)
    print("\n== pool de threads ==")
    pools(n, cpus)


if __name__ == "__main__":
    main()
