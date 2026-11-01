"""bench_mvp.py -- mede o MVP (v0.1.0) com repetições, para a régua de `bench.py` (média, desvio e intervalo de 95%).

Roda no ambiente do MVP (o repositório fake-data, com o kernel dele compilado), e grava as medidas aqui:

    uv run --project ..\\fake-data python tools/bench_mvp.py ..\\fake-data              # 100 repetições
    uv run --project ..\\fake-data python tools/bench_mvp.py ..\\fake-data --runs 30

Mesmos casos, tamanhos e parâmetros de `bench.py` (5 milhões de linhas; 1 milhão na tabela e nos endereços), com 1
thread e com todas. Antes das repetições, uma rodada de aquecimento (bases e caches). Grava `tools/mvp_stats.json`,
que `bench.py` e `pytest -m bench` usam no lugar dos números fixos.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from benchstats import summarize  # noqa: E402

OUT = HERE / "mvp_stats.json"
SEED = 2026


def cases(g: Any) -> list[tuple[str, Callable[..., Any], int]]:
    """(nome em bench.py, função(n, threads=...), divisor de n)."""
    sex_cache: dict[int, Any] = {}

    def by_sex(n: int, **k: Any) -> Any:
        if n not in sex_cache:  # a coluna de sexo fica pronta antes, como em bench.py
            sex_cache[n] = g.sex(n, rng=1)
        return g.first_name(n, sex=sex_cache[n], rng=SEED, **k)

    table_20 = {
        "cpf": ("cpf", {"formatted": True}), "cnpj": "cnpj", "sexo": "sex",
        "nome": ("first_name", {"sex": g.ref("sexo")}), "sobrenome": "last_name", "email": "email",
        "telefone": "phone", "idade": ("age", {"low": 18, "high": 90}),
        "nasc": ("birthdate", {"age": g.ref("idade"), "on": "2026-01-01"}),
        "renda": ("correlated", {"other": g.ref("idade"), "rho": 0.5, "mean": 8, "std": 0.6, "lognormal": True}),
        "cep": "cep", "uuid": "uuid4", "ip": "ipv4", "placa": "placa", "empresa": "empresa",
        "obs": ("sentence", {"null_fraction": 0.3}), "ativo": "bool", "valor": "float", "qtd": "int", "data": "date",
    }  # fmt: skip
    return [
        ("integer", lambda n, **k: g.integer(n, 0, 1000, rng=SEED, **k), 1),
        ("uniform", lambda n, **k: g.uniform(n, rng=SEED, **k), 1),
        ("normal", lambda n, **k: g.normal(n, rng=SEED, **k), 1),
        ("lognormal", lambda n, **k: g.lognormal(n, rng=SEED, **k), 1),
        ("boolean", lambda n, **k: g.boolean(n, rng=SEED, **k), 1),
        ("date", lambda n, **k: g.date(n, rng=SEED, **k), 1),
        ("datetime", lambda n, **k: g.datetime(n, rng=SEED, **k), 1),
        ("sex", lambda n, **k: g.sex(n, rng=SEED, **k), 1),
        ("age", lambda n, **k: g.age(n, rng=SEED, **k), 1),
        ("first_name", lambda n, **k: g.first_name(n, rng=SEED, **k), 1),
        ("first_name_by_sex", by_sex, 1),
        ("last_name", lambda n, **k: g.last_name(n, rng=SEED, **k), 1),
        ("sentence", lambda n, **k: g.sentence(n, rng=SEED, **k), 1),
        ("cep", lambda n, **k: g.cep(n, formatted=True, rng=SEED, **k), 1),
        ("address", lambda n, **k: g.address(n, rng=SEED, **k), 5),
        ("address_full", lambda n, **k: g.address(n, full=True, phone=True, coords=True, rng=SEED, **k), 5),
        ("table_20col", lambda n, **k: g.table(n, table_20, seed=SEED, **k), 5),
    ]


def runs_of(fn: Callable[..., Any], n: int, runs: int, **kw: Any) -> list[float]:
    fn(min(n, 100_000), **kw)  # aquecimento
    out = []
    for _ in range(runs):
        gc.collect()
        gc.disable()
        try:
            t0 = time.perf_counter()
            fn(n, **kw)
            out.append((time.perf_counter() - t0) / n * 1e9)
        finally:
            gc.enable()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mvp", type=Path, help="pasta do repositório do MVP (fake-data)")
    ap.add_argument("-n", type=int, default=5_000_000)
    ap.add_argument("--runs", type=int, default=100)
    ap.add_argument("--kinds", nargs="*", help="só estes casos")
    args = ap.parse_args()
    sys.path.insert(0, str(args.mvp.resolve()))
    os.chdir(args.mvp)  # o MVP acha as bases pelo caminho relativo
    import generators as g  # noqa: PLC0415  # pyright: ignore[reportMissingImports]

    threads = os.cpu_count() or 1
    results: dict[str, Any] = {}
    if OUT.exists():  # rodar só alguns casos atualiza esses e mantém os outros
        results = json.loads(OUT.read_text(encoding="utf-8")).get("cases", {})
    print(f"MVP · N = {args.n:,} · {args.runs} repetições · {threads} threads · Python {platform.python_version()}")
    print(f"{'caso':<20}{'1 thread':>18}{f'{threads} threads':>18}   (média ± meia largura do IC 95%, ns/linha)")
    for name, fn, div in cases(g):
        if args.kinds and name not in args.kinds:
            continue
        n = max(args.n // div, 1_000)
        one = summarize(runs_of(fn, n, args.runs))
        many = summarize(runs_of(fn, n, args.runs, threads=threads))
        results[name] = {"n_rows": n, "one": one.as_dict(), "many": many.as_dict()}
        print(f"{name:<20}{one!s:>18}{many!s:>18}", flush=True)
        OUT.write_text(
            json.dumps(
                {
                    "info": {
                        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "threads": threads,
                        "python": platform.python_version(),
                        "platform": platform.platform(),
                        "runs": args.runs,
                    },
                    "cases": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
