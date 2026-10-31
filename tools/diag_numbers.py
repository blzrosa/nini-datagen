"""diag_numbers.py -- separa o custo de `integer` em partes, para achar de onde vem a diferença para o MVP.

uv run python tools/diag_numbers.py
"""

from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np
import polars as pl

import nini_datagen as dg
from nini_datagen import _native
from nini_datagen.core.rng import seed_state

N = 5_000_000
BLOCK = 65_536


def best(f: Callable[[], object], repeats: int = 5) -> str:
    t_best = float("inf")
    for _ in range(repeats):
        t = time.perf_counter()
        f()
        t_best = min(t_best, time.perf_counter() - t)
    return f"{t_best / N * 1e9:6.2f} ns/linha"


def main() -> None:
    lib = _native.lib()
    st = seed_state(1, "diag")
    warm = np.zeros(N, np.int32)
    kernel = lib.dg_rand_i32

    def per_block() -> list[np.ndarray]:
        out = []
        for i in range(0, N, BLOCK):
            a = np.empty(min(BLOCK, N - i), np.int32)
            kernel(st.ctypes.data, 0, 1001, len(a), a.ctypes.data)
            out.append(a)
        return out

    def reused() -> None:
        kernel(st.ctypes.data, 0, 1001, N, warm.ctypes.data)

    def fresh() -> np.ndarray:
        a = np.empty(N, np.int32)  # guardar em variável: um temporário seria liberado antes de o C++ escrever
        kernel(st.ctypes.data, 0, 1001, N, a.ctypes.data)
        return a

    rows = [
        ("1. kernel, array já usado (sem falta de página)", reused),
        ("2. kernel, array novo de 20 MB", fresh),
        ("3. kernel, blocos novos de 65.536 (como o MVP)", per_block),
        ("4. pl.Series(array pronto)", lambda: pl.Series("x", warm)),
        ("5. g.integer (tudo)", lambda: dg.DataGen(seed=1, threads=1).integer(N, low=0, high=1000)),
    ]
    for label, f in rows:
        print(f"{label:<50} {best(f)}")


if __name__ == "__main__":
    main()
