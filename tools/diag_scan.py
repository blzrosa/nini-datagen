"""diag_scan.py -- por que o `scan` com muitas threads é mais lento que o `table` (diagnóstico para a 0.2.1).

    uv run python tools/diag_scan.py              # 1 milhão de linhas da tabela de 20 colunas
    uv run python tools/diag_scan.py -n 2000000

Cada variante roda num processo novo (``POLARS_MAX_THREADS`` só vale se definido antes de importar o Polars), com
aquecimento e o melhor de 3. Mostra, em ns por linha:

* ``parede``: o tempo total da operação;
* ``na fonte``: o tempo gasto dentro do gerador de lotes (`scan_source`), isto é, gerando os dados; a diferença para
  a parede é o que o Polars faz fora dele (juntar os lotes, esperar, trocar de thread).

Se ``na fonte`` sobe com o scan (em relação à fonte sozinha), as threads do Polars estão disputando os núcleos com as
da geração; se fica igual e só a parede sobe, o custo está na montagem do resultado do lado do Polars.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# (rótulo, opções): mode = table | source | scan; engine = auto | streaming | in-memory; head = usa .head(n)
VARIANTS: list[tuple[str, dict[str, Any]]] = [
    ("table", {"mode": "table"}),
    ("fonte sozinha (sem o Polars)", {"mode": "source"}),
    ("scan .head(n) engine=auto", {"mode": "scan"}),
    ("scan .head(n) engine=streaming", {"mode": "scan", "engine": "streaming"}),
    ("scan .head(n) engine=in-memory", {"mode": "scan", "engine": "in-memory"}),
    ("scan(n) sem head", {"mode": "scan", "head": False}),
    ("scan POLARS_MAX_THREADS=4", {"mode": "scan", "polars_threads": 4}),
    ("scan POLARS_MAX_THREADS=1", {"mode": "scan", "polars_threads": 1}),
    ("scan threads da geração = 8", {"mode": "scan", "dg_threads": 8}),
    ("table threads da geração = 8", {"mode": "table", "dg_threads": 8}),
    ("scan batch_size=262144", {"mode": "scan", "batch": 262_144}),
    ("scan batch_size=4194304", {"mode": "scan", "batch": 4_194_304}),
    ("scan threads=1 (referência)", {"mode": "scan", "dg_threads": 1}),
    ("table threads=1 (referência)", {"mode": "table", "dg_threads": 1}),
]


def child(opts: dict[str, Any], n: int) -> dict[str, Any]:
    sys.path.insert(0, str(HERE))
    import polars as pl  # noqa: PLC0415

    import nini_datagen as dg  # noqa: PLC0415
    from bench import TABLE_20  # noqa: PLC0415
    from nini_datagen.core.blocks import resolve_threads  # noqa: PLC0415
    from nini_datagen.schema import lazy  # noqa: PLC0415

    spent = [0.0]
    original = lazy.scan_source

    def timed_source(*a: Any, **k: Any) -> Any:  # cronometra só o tempo dentro do gerador de lotes
        it = original(*a, **k)
        while True:
            t0 = time.perf_counter()
            try:
                batch = next(it)
            except StopIteration:
                spent[0] += time.perf_counter() - t0
                return
            spent[0] += time.perf_counter() - t0
            yield batch

    lazy.scan_source = timed_source
    g = dg.DataGen(seed=1, threads=opts.get("dg_threads"))
    mode, batch, engine = opts["mode"], opts.get("batch"), opts.get("engine", "auto")
    bound = TABLE_20.bind(g.locale)

    def once() -> None:
        if mode == "table":
            g.table(n, TABLE_20)
        elif mode == "source":
            for _ in timed_source(bound, g._ctx, 10**9, None, None, n, batch):
                pass
        else:
            if opts.get("head", True):
                lf = g.scan(10**9, TABLE_20, batch_size=batch).head(n)
            else:
                lf = g.scan(n, TABLE_20, batch_size=batch)
            df = lf.collect(engine=engine)
            assert df.height == n

    once()  # aquecimento (tabelas, caches, threads)
    best_wall, best_src = float("inf"), float("inf")
    for _ in range(3):
        spent[0] = 0.0
        t0 = time.perf_counter()
        once()
        wall = time.perf_counter() - t0
        if wall < best_wall:
            best_wall, best_src = wall, spent[0]
    return {
        "wall": best_wall / n * 1e9,
        "src": best_src / n * 1e9 if mode != "table" else None,
        "polars": pl.__version__,
        "pl_threads": pl.thread_pool_size(),
        "dg_threads": resolve_threads(g.threads),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=1_000_000)
    ap.add_argument("--child", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.child:
        print(json.dumps(child(json.loads(args.child), args.n)))
        return
    print(f"== scan x table, tabela de 20 colunas, {args.n:,} linhas (ns/linha; melhor de 3) ==")
    first = True
    for label, opts in VARIANTS:
        env = dict(os.environ)
        env.pop("POLARS_MAX_THREADS", None)
        if "polars_threads" in opts:
            env["POLARS_MAX_THREADS"] = str(opts["polars_threads"])
        cmd = [sys.executable, __file__, "-n", str(args.n), "--child", json.dumps(opts)]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            err = (proc.stderr.strip().splitlines() or ["?"])[-1]
            print(f"{label:<34} falhou: {err}")
            continue
        r = json.loads(proc.stdout.strip().splitlines()[-1])
        if first:
            print(f"Polars {r['polars']}; threads: {r['pl_threads']} do Polars, {r['dg_threads']} da geração")
            print(f"{'variante':<34}{'parede':>9}{'na fonte':>10}{'fora':>9}   threads (Polars/geração)")
            first = False
        src = r["src"]
        out = "" if src is None else f"{src:10.1f}{r['wall'] - src:9.1f}"
        print(f"{label:<34}{r['wall']:9.1f}{out:<19}   {r['pl_threads']}/{r['dg_threads']}")


if __name__ == "__main__":
    main()
