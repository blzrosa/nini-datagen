"""bench.py -- mede ns por linha de cada gerador e compara com o MVP (v0.1.0).

    uv run python tools/bench.py                 # 5 milhões de linhas, 1 thread e todas
    uv run python tools/bench.py -n 1000000 --kinds integer first_name
    uv run python tools/bench.py --markdown bench.md

A régua é a do plano: nenhum gerador mais de 10% mais lento que o MVP com 1 thread. Os números do MVP são os do
benchmark final de 30/10/2026 no PC da Nini (Windows 11, 16 threads, Python 3.14, Polars 2.0, 5M linhas); em outra
máquina a comparação só vale como ordem de grandeza.

O MVP foi compilado com clang (zig c++) e -march=native. Para comparar na mesma base no Windows:

    $env:DG_CLANGCL = "1"; $env:DG_NATIVE = "ON"; uv sync; uv run python tools/bench.py

(Os wheels publicados usam clang-cl com x86-64-v2, sem -march=native, e escolhem na hora a cópia AVX2 dos laços de
normal, lognormal e correlated.) O build local padrão no Windows é com o MSVC, que não tem essa cópia: nele, lognormal
fica mais lento que o MVP e conta como exceção. Para medir como nos wheels, use $env:DG_CLANGCL = "1".

Cada caso é medido 10 vezes (``--runs``) e comparado com o MVP pela razão das médias com intervalo de 95%
(`benchstats.py`); a referência do MVP é `mvp_stats.json` (`bench_mvp.py`, 100 repetições).
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
from dataclasses import dataclass
from pathlib import Path

import polars as pl

import nini_datagen as dg

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchstats import Stats, compare, summarize

# MVP: (1 thread, 16 threads) em ns/linha, do benchmark final (melhor de 3). Valem só sem `tools/mvp_stats.json`
# (gravado por bench_mvp.py, com média e desvio de muitas repetições), que é a referência preferida.
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
    "sentence": (78.1, 15.7),
    "cep": (60.8, 60.1),
    "address": (187.4, 187.5),
    "address_full": (443.5, 420.8),
    "table_20col": (320.5, 165.7),
}
TOLERANCE = 1.10
RUNS = 10  # repetições por caso (média, desvio e intervalo de 95%)
MVP_STATS = Path(__file__).resolve().parent / "mvp_stats.json"

# geradores que ficam mais lentos que o MVP por decisão de projeto (contam como exceção, não como regressão)
EXCEPTIONS: dict[str, str] = {}


def _simd_active() -> bool:
    from nini_datagen._native import lib  # noqa: PLC0415

    return bool(lib().dg_simd(-1))


# sem a cópia AVX2 dos laços (CPU sem AVX2, build com o MSVC ou fora do x86-64), o exp próprio fica abaixo do MVP
if not _simd_active():
    EXCEPTIONS["lognormal"] = "sem AVX2 neste build (MSVC, CPU ou arquitetura): o exp próprio, sem FMA, roda 2 por vez"


@dataclass
class Case:
    name: str
    run: Callable[[dg.DataGen, int], pl.Series | pl.DataFrame]
    scale: int = 1  # casos pesados medem com n / scale linhas (como no MVP)


# a tabela de 20 colunas do benchmark final do MVP (mesmos tipos, mesmos parâmetros)
TABLE_20 = dg.Schema(
    {
        "cpf": ("cpf", {"formatted": True}),
        "cnpj": "cnpj",
        "sexo": "sex",
        "nome": ("first_name", {"sex": dg.ref("sexo")}),
        "sobrenome": "last_name",
        "email": "email",
        "telefone": "phone",
        "idade": ("age", {"low": 18, "high": 90}),
        "nasc": ("birthdate", {"age": dg.ref("idade"), "on": "2026-01-01"}),
        "renda": ("correlated", {"other": dg.ref("idade"), "rho": 0.5, "mean": 8, "std": 0.6, "lognormal": True}),
        "cep": "cep",
        "uuid": "uuid",
        "ip": "ipv4",
        "placa": "license_plate",
        "empresa": "company",
        "obs": ("sentence", {"null_fraction": 0.3}),
        "ativo": "boolean",
        "valor": "uniform",
        "qtd": "integer",
        "data": "date",
    }
)


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
    Case("cpf", lambda g, n: g.cpf(n)),
    Case("cpf_formatted", lambda g, n: g.cpf(n, formatted=True)),
    Case("cpf_unique", lambda g, n: g.cpf(n, unique=True)),
    Case("cnpj", lambda g, n: g.cnpj(n)),
    Case("cnpj_alnum", lambda g, n: g.cnpj(n, alphanumeric=True)),
    Case("pis", lambda g, n: g.pis(n)),
    Case("voter_id", lambda g, n: g.voter_id(n)),
    Case("cnh", lambda g, n: g.cnh(n)),
    Case("rg", lambda g, n: g.rg(n)),
    Case("license_plate", lambda g, n: g.license_plate(n)),
    Case("credit_card", lambda g, n: g.credit_card(n)),
    Case("iban", lambda g, n: g.iban(n)),
    Case("ean13", lambda g, n: g.ean13(n)),
    Case("uuid", lambda g, n: g.uuid(n)),
    Case("ipv4", lambda g, n: g.ipv4(n)),
    Case("ipv6", lambda g, n: g.ipv6(n)),
    Case("mac", lambda g, n: g.mac(n)),
    Case("url", lambda g, n: g.url(n)),
    Case("phone", lambda g, n: g.phone(n)),
    Case("phone_masked", lambda g, n: g.phone(n, style="masked")),
    Case("email", lambda g, n: g.email(n)),
    Case("username", lambda g, n: g.username(n)),
    Case("company", lambda g, n: g.company(n)),
    Case("vehicle", lambda g, n: g.vehicle(n)),
    Case("occupation", lambda g, n: g.occupation(n)),
    Case("sentence", lambda g, n: g.sentence(n)),
    Case("paragraph", lambda g, n: g.paragraph(n)),
    Case("cep", lambda g, n: g.cep(n)),
    Case("address", lambda g, n: g.address(n), scale=5),
    Case("address_full", lambda g, n: g.address(n, full=True), scale=5),
    Case("city", lambda g, n: g.city(n)),
    Case("table_20col", lambda g, n: g.table(n, TABLE_20), scale=5),
    Case("scan_20col_head", lambda g, n: g.scan(10**9, TABLE_20).head(n).collect(), scale=5),
]


def measure_runs(case: Case, n: int, threads: int, runs: int = RUNS) -> Stats:
    """``runs`` medidas (ns/linha) depois de uma rodada de aquecimento (bases e caches), sem o coletor de lixo."""
    g = dg.DataGen(seed=1, threads=threads)
    n = max(n // case.scale, 1_000)
    case.run(g, min(n, 100_000))
    samples = []
    for _ in range(runs):
        gc.collect()
        gc.disable()
        try:
            t = time.perf_counter()
            s = case.run(g, n)
            samples.append((time.perf_counter() - t) / n * 1e9)
        finally:
            gc.enable()
        assert len(s) == n
    return summarize(samples)


def measure(case: Case, n: int, threads: int, repeats: int = 3) -> float:
    """Média de ``repeats`` medidas (ns/linha); para o diagnóstico rápido de outras ferramentas."""
    return measure_runs(case, n, threads, repeats).mean


def mvp_reference() -> tuple[dict[str, tuple[Stats, Stats]], str]:
    """Referência do MVP por caso, ``(1 thread, todas)``: de `mvp_stats.json` se existir, senão os números fixos."""
    if MVP_STATS.exists():
        data = json.loads(MVP_STATS.read_text(encoding="utf-8"))
        out = {
            k: (Stats(v["one"]["mean"], v["one"]["sd"], v["one"]["n"]), Stats(v["many"]["mean"], v["many"]["sd"],
                v["many"]["n"]))
            for k, v in data["cases"].items()
        }  # fmt: skip
        info = data.get("info", {})
        return out, f"{MVP_STATS.name} ({info.get('runs', '?')} repetições, {info.get('date', '?')})"
    return {k: (Stats(a, 0.0, 1), Stats(b, 0.0, 1)) for k, (a, b) in MVP.items()}, "números fixos (melhor de 3)"


def verdict(name: str, new: Stats, ref: Stats) -> tuple[str, bool]:
    """Texto da situação e se conta como regressão (``mais lento`` fora das exceções)."""
    ratio, lo, hi, status = compare(new, ref, TOLERANCE)
    interval = f"{ratio:.2f}x [{lo:.2f}, {hi:.2f}]"
    if status == "mais lento" and name in EXCEPTIONS:
        return f"{interval} exceção: {EXCEPTIONS[name]}", False
    if status == "mais lento":
        return f"**{interval} mais lento**", True
    return f"{interval} {status}", False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=5_000_000)
    ap.add_argument("--kinds", nargs="*", help="só estes casos")
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 1, help="threads da segunda coluna")
    ap.add_argument("--markdown", help="também grava a tabela neste arquivo")
    ap.add_argument("--runs", type=int, default=RUNS, help="repetições por caso")
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
        f"| gerador | 1 thread | {args.threads} threads | MVP 1 thread | MVP 16 threads | novo / MVP [IC 95%] |",
        "|---|---:|---:|---:|---:|---|",
    ]
    ref, source = mvp_reference()
    lines.insert(3, f"{args.runs} repetições por caso (média ± meia largura do IC 95%, ns/linha); MVP: {source}")
    print("\n".join(lines[2:4]))
    print(lines[-2])
    worse = []
    for c in cases:
        one = measure_runs(c, args.n, 1, args.runs)
        many = measure_runs(c, args.n, args.threads, args.runs)
        mvp = ref.get(c.name)
        if mvp is None:
            status = "sem referência"
        else:
            status, bad = verdict(c.name, one, mvp[0])
            if bad:
                worse.append(c.name)
        m1, m16 = (str(mvp[0]), str(mvp[1])) if mvp else ("", "")
        row = f"| {c.name} | {one} | {many} | {m1} | {m16} | {status} |"
        lines.append(row)
        print(row, flush=True)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    if worse:
        print(f"\nmais lentos que o MVP (+{TOLERANCE - 1:.0%}, com 95% de confiança): {', '.join(worse)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
