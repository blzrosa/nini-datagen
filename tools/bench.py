"""bench.py -- mede ns por linha de cada gerador e compara com o MVP (v0.1.0).

    uv run python tools/bench.py                 # 5 milhões de linhas, 1 thread e todas
    uv run python tools/bench.py -n 1000000 --kinds integer first_name
    uv run python tools/bench.py --markdown bench.md

A régua é a do plano: nenhum gerador mais de 10% mais lento que o MVP com 1 thread. Os números do MVP são os do
benchmark final de 30/10/2026 no PC da Nini (Windows 11, 16 threads, Python 3.14, Polars 2.0, 5M linhas); em outra
máquina a comparação só vale como ordem de grandeza.

O MVP foi compilado com clang (zig c++) e -march=native. Para comparar na mesma base no Windows:

    $env:DG_CLANGCL = "1"; $env:DG_NATIVE = "ON"; uv sync; uv run python tools/bench.py

(Os wheels publicados usam clang-cl com x86-64-v2, sem -march=native.) normal e lognormal não chegam no MVP de
propósito: a versão nova não usa FMA nem o log da biblioteca do sistema, para a mesma semente dar os mesmos bits em
qualquer máquina.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

import polars as pl

import nini_datagen as dg

# MVP: (1 thread, 16 threads) em ns/linha
MVP: dict[str, tuple[float, float]] = {
    "integer": (1.2, 1.1),
    "uniform": (1.3, 1.5),
    "normal": (3.5, 1.4),
    "lognormal": (4.3, 1.6),
    "boolean": (0.2, 1.2),
    "date": (1.2, 1.3),
    "datetime": (1.2, 1.3),
    "sex": (4.3, 2.6),
    "age": (2.1, 1.6),
    "first_name": (5.4, 2.7),
    "first_name_by_sex": (6.2, 3.4),
    "last_name": (4.9, 3.0),
}
TOLERANCE = 1.10


@dataclass
class Case:
    name: str
    run: Callable[[dg.DataGen, int], pl.Series]


def _by_sex() -> Callable[[dg.DataGen, int], pl.Series]:
    cache: dict[int, pl.Series] = {}

    def run(g: dg.DataGen, n: int) -> pl.Series:
        if n not in cache:  # a coluna de sexo fica pronta antes (o MVP media do mesmo jeito)
            cache[n] = dg.DataGen(seed=1).sex(n)
        return g.first_name(n, sex=cache[n])

    return run


CASES = [
    Case("integer", lambda g, n: g.integer(n, low=0, high=1000)),
    Case("uniform", lambda g, n: g.uniform(n)),
    Case("normal", lambda g, n: g.normal(n)),
    Case("lognormal", lambda g, n: g.lognormal(n)),
    Case("boolean", lambda g, n: g.boolean(n)),
    Case("date", lambda g, n: g.date(n)),
    Case("datetime", lambda g, n: g.datetime(n)),
    Case("choice", lambda g, n: g.choice(n, [f"categoria {i}" for i in range(50)])),
    Case("sex", lambda g, n: g.sex(n)),
    Case("age", lambda g, n: g.age(n)),
    Case("first_name", lambda g, n: g.first_name(n)),
    Case("first_name_by_sex", _by_sex()),
    Case("last_name", lambda g, n: g.last_name(n)),
    Case("full_name", lambda g, n: g.full_name(n)),
]


def measure(case: Case, n: int, threads: int, repeats: int = 3) -> float:
    """Melhor de ``repeats`` (ns/linha), depois de uma rodada de aquecimento (carrega bases e caches)."""
    g = dg.DataGen(seed=1, threads=threads)
    case.run(g, min(n, 100_000))
    best = float("inf")
    for _ in range(repeats):
        t = time.perf_counter()
        s = case.run(g, n)
        best = min(best, time.perf_counter() - t)
        assert len(s) == n
    return best / n * 1e9


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=5_000_000)
    ap.add_argument("--kinds", nargs="*", help="só estes casos")
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 1, help="threads da segunda coluna")
    ap.add_argument("--markdown", help="também grava a tabela neste arquivo")
    args = ap.parse_args(argv)

    cases = [c for c in CASES if not args.kinds or c.name in args.kinds]
    build = f"DG_CLANGCL={os.environ.get('DG_CLANGCL', '')!r} DG_NATIVE={os.environ.get('DG_NATIVE', '')!r}"
    head = (
        f"N = {args.n:,} · {args.threads} threads · Python {platform.python_version()} · Polars {pl.__version__} · "
        f"{platform.platform()} · {build}"
    )
    lines = [
        "# Benchmark do nini-datagen",
        "",
        head,
        "",
        f"| gerador | 1 thread | {args.threads} threads | MVP 1 thread | MVP {16} threads | situação |",
        "|---|---:|---:|---:|---:|---|",
    ]
    print(head)
    worse = []
    for c in cases:
        one = measure(c, args.n, 1)
        many = measure(c, args.n, args.threads)
        mvp = MVP.get(c.name)
        if mvp is None:
            status = "sem referência"
        elif one <= mvp[0] * TOLERANCE:
            status = "ok"
        else:
            status = f"**{one / mvp[0]:.2f}x o MVP**"
            worse.append(c.name)
        m1, m16 = (f"{mvp[0]:.1f}", f"{mvp[1]:.1f}") if mvp else ("", "")
        row = f"| {c.name} | {one:.2f} | {many:.2f} | {m1} | {m16} | {status} |"
        lines.append(row)
        print(row, flush=True)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    if worse:
        print(f"\nmais lentos que o MVP (+{TOLERANCE - 1:.0%}): {', '.join(worse)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
