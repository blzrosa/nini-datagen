"""profile_table.py -- de onde vem o tempo da tabela de 20 colunas e dos endereços (diagnóstico de desempenho).

    uv run python tools/profile_table.py              # 1 milhão de linhas
    uv run python tools/profile_table.py -n 2000000

Mostra, em ns por linha:

1. cada coluna da tabela do benchmark sozinha (`generate`), separando o planejamento (`prepare`, só na thread
   principal), o preenchimento dos blocos (`fill`) e a montagem da Series (`finish`, inclui os dados sujos);
2. a tabela inteira com 1 thread e com todas, e quanto do tempo é preenchimento;
3. `cep` e `address` com a base leve (``source="lite"``) e com a completa (se baixada), para separar o custo da base
   grande (acessos aleatórios a uma tabela que não cabe no cache) do custo do código.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import nini_datagen as dg
from bench import TABLE_20
from nini_datagen.core.blocks import split
from nini_datagen.registry import registry
from nini_datagen.schema import Column


def best(fn, repeats: int = 3) -> float:
    t = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        t = min(t, time.perf_counter() - t0)
    return t


def columns(g: dg.DataGen, n: int) -> None:
    schema = TABLE_20.bind(g.locale)
    built = schema.run(g._ctx, n)  # entradas das colunas com ref (sexo, idade)
    blocks = split(n)
    print(f"\n== colunas da tabela ({n:,} linhas, 1 thread) ==")
    print(f"{'coluna':<12}{'tipo':<16}{'prepare':>9}{'fill':>9}{'finish':>9}{'total':>9}")
    total = 0.0
    for name in schema.names:
        spec = schema[name]
        if not isinstance(spec, Column):
            continue
        provider = registry.get(spec.kind)
        cfg = spec.config  # fora do lambda: dentro dele o pyright perde o isinstance
        inputs = {k: built[r.column] for k, r in spec.refs.items()}
        if provider.composite:
            t = best(lambda: provider.generate(n, cfg, g._ctx, inputs))  # noqa: B023
            print(f"{name:<12}{spec.kind:<16}{'':>9}{'':>9}{'':>9}{t / n * 1e9:9.1f}")
            total += t
            continue
        times = [float("inf")] * 3
        for _ in range(3):
            t0 = time.perf_counter()
            p = provider.prepare(n, cfg, g._ctx, inputs)
            t1 = time.perf_counter()
            for b in blocks:
                p.fill(b)
            t2 = time.perf_counter()
            p.finish()
            t3 = time.perf_counter()
            times = [min(a, b) for a, b in zip(times, (t1 - t0, t2 - t1, t3 - t2), strict=True)]
        ns = [x / n * 1e9 for x in times]
        total += sum(times)
        print(f"{name:<12}{spec.kind:<16}{ns[0]:9.1f}{ns[1]:9.1f}{ns[2]:9.1f}{sum(ns):9.1f}")
    print(f"{'soma':<28}{'':>27}{total / n * 1e9:9.1f}")


def table(n: int) -> None:
    """A tabela inteira, com o tempo de cada etapa de `Schema.run` (somado entre as threads quando em paralelo)."""
    from nini_datagen.providers.base import Prepared, Provider  # noqa: PLC0415
    from nini_datagen.schema import plan, scan_source  # noqa: PLC0415

    spent = {"prepare": 0.0, "fill": 0.0, "finish": 0.0}

    def timed(key: str, fn: Any) -> Any:
        def wrapper(*a: Any, **k: Any) -> Any:
            t0 = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                spent[key] += time.perf_counter() - t0

        return wrapper

    originals = (Provider.prepare, plan._fill, Prepared.finish)
    print(f"\n== tabela inteira ({n:,} linhas; ns/linha) ==")
    print("etapas: prepare e finish somam o tempo de cada coluna (em paralelo, a soma passa do tempo de parede)")
    for threads in (1, os.cpu_count() or 1):
        g = dg.DataGen(seed=1, threads=threads)
        g.table(min(n, 100_000), TABLE_20)
        t = best(lambda: g.table(n, TABLE_20))  # noqa: B023
        lf = best(lambda: g.scan(10**9, TABLE_20).head(n).collect())  # noqa: B023
        bound = TABLE_20.bind(g.locale)
        src = best(lambda: list(scan_source(bound, g._ctx, 10**9, None, None, n, None)))  # noqa: B023
        Provider.prepare = timed("prepare", originals[0])  # type: ignore[method-assign]
        plan._fill = timed("fill", originals[1])
        Prepared.finish = timed("finish", originals[2])  # type: ignore[method-assign]
        try:
            for k in spent:
                spent[k] = 0.0
            t0 = time.perf_counter()
            g.table(n, TABLE_20)
            wall = time.perf_counter() - t0
        finally:
            Provider.prepare, plan._fill, Prepared.finish = originals  # type: ignore[method-assign]
        parts = "  ".join(f"{k} {v / n * 1e9:6.1f}" for k, v in spent.items())
        print(
            f"threads={threads:<3} table {t / n * 1e9:7.1f}   scan+head {lf / n * 1e9:7.1f}   "
            f"(só a fonte, sem o Polars: {src / n * 1e9:7.1f})   "
            f"[{parts}  parede {wall / n * 1e9:6.1f}]"
        )


def addresses(n: int) -> None:
    print(f"\n== endereços ({n:,} linhas) ==")
    have_full = dg.datasets.path("cnefe") is not None
    for source in ("lite", "full") if have_full else ("lite",):
        for threads in (1, os.cpu_count() or 1):
            g = dg.DataGen(seed=1, threads=threads)
            g.cep(1000, source=source)
            g.address(1000, source=source)
            tc = best(lambda: g.cep(n, source=source))  # noqa: B023
            ta = best(lambda: g.address(n, source=source))  # noqa: B023
            tf = best(lambda: g.address(n, source=source, full=True))  # noqa: B023
            print(
                f"{source:<5} threads={threads:<3} cep {tc / n * 1e9:6.1f}  address {ta / n * 1e9:6.1f}  "
                f"address_full {tf / n * 1e9:6.1f} ns/linha"
            )
    if not have_full:
        print("(base completa não baixada: rode nini_datagen.datasets.download('cnefe') para comparar)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=1_000_000)
    args = ap.parse_args()
    columns(dg.DataGen(seed=1, threads=1), args.n)
    table(args.n)
    addresses(args.n * 5)


if __name__ == "__main__":
    main()
