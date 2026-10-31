"""compare.py -- nini-datagen contra Faker, Mimesis e dataforge, gerador a gerador (desempenho e validade).

    # num ambiente temporário com Python 3.14 (o dataforge-py pede >= 3.12), sem mexer no .venv do projeto:
    uv run --isolated --python 3.14 --group bench python tools/compare.py --markdown benchmarks/comparacao.md

Regras da comparação (iguais para todas as bibliotecas):

* o resultado de cada uma é uma coluna do Polars (``pl.Series``) com ``n`` valores: para as bibliotecas que geram um
  valor por chamada, a medida inclui montar a lista e converter, que é o que quem usa precisa fazer;
* locale pt_BR e semente fixa em todas; 1 thread no nini-datagen (``threads=1``), para não comparar paralelismo;
* melhor de 3 execuções; as bibliotecas valor-a-valor são medidas com menos linhas (``--n-slow``) e o resultado é
  normalizado em ns por linha;
* "válidos": fração de uma amostra que passa na regra brasileira (dígitos verificadores de CPF, CNPJ, EAN-13, cartão e
  IBAN do Brasil; formato de CEP, telefone, placa e IPv4 público). Gerador que a biblioteca não tem aparece como "—".

Uma biblioteca que não está instalada é pulada (a coluna dela fica vazia), então o script roda com o que houver.
"""

from __future__ import annotations

import argparse
import gc
import ipaddress
import math
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import polars as pl

import nini_datagen as dg
from nini_datagen import validators as val

Gen = Callable[[int], Any]


# ------------------------------------------------------------------ validadores de formato
def _re(pattern: str) -> Callable[[str], bool]:
    rx = re.compile(pattern)
    return lambda s: bool(rx.fullmatch(s))


def _ipv4_public(s: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(s)
    except ValueError:
        return False
    return ip.is_global


def _iban_br(s: str) -> bool:
    return s.replace(" ", "").startswith("BR") and val.iban(s)


CHECKS: dict[str, Callable[[str], bool]] = {
    "cpf": val.cpf,
    "cnpj": val.cnpj,
    "ean13": val.ean13,
    "credit_card": val.credit_card,
    "iban": _iban_br,
    "cep": _re(r"\d{5}-?\d{3}"),
    "phone": _re(r"(\+55 ?)?\(?\d{2}\)? ?9?\d{4}-?\d{4}"),
    "license_plate": _re(r"[A-Z]{3}-?\d[A-Z0-9]\d{2}"),
    "ipv4": _ipv4_public,
    "email": _re(r"[^@\s]+@[^@\s]+\.[a-z]{2,}"),
    "uuid": _re(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"),
}


# ------------------------------------------------------------------ bibliotecas
@dataclass
class Library:
    name: str
    vectorized: bool  # gera a coluna inteira de uma vez (senão, um valor por chamada)
    cases: dict[str, Gen] = field(default_factory=dict)
    version: str = ""


def _per_value(fn: Callable[[], Any]) -> Gen:
    return lambda n: pl.Series([fn() for _ in range(n)])


def nini() -> Library:
    g = dg.DataGen(seed=1, threads=1)
    cases: dict[str, Gen] = {
        "first_name": g.first_name,
        "last_name": g.last_name,
        "full_name": g.full_name,
        "city": g.city,
        "email": g.email,
        "username": g.username,
        "phone": lambda n: g.phone(n, style="masked"),
        "cep": lambda n: g.cep(n, formatted=True),
        "address": lambda n: g.address(n, full=True).struct.field("full"),
        "cpf": lambda n: g.cpf(n, formatted=True),
        "cnpj": lambda n: g.cnpj(n, formatted=True),
        "uuid": g.uuid,
        "ipv4": g.ipv4,
        "ipv6": g.ipv6,
        "mac": g.mac,
        "url": g.url,
        "sentence": g.sentence,
        "company": g.company,
        "license_plate": g.license_plate,
        "ean13": g.ean13,
        "iban": g.iban,
        "credit_card": g.credit_card,
        "boolean": g.boolean,
        "date": g.date,
        "integer": lambda n: g.integer(n, low=0, high=1000),
    }
    return Library("nini-datagen", True, cases, dg.__version__)


def faker() -> Library | None:
    try:
        import faker as faker_mod  # noqa: PLC0415  # pyright: ignore[reportMissingImports]
    except ImportError:
        return None
    f = faker_mod.Faker("pt_BR")
    faker_mod.Faker.seed(1)
    cases = {
        "first_name": _per_value(f.first_name),
        "last_name": _per_value(f.last_name),
        "full_name": _per_value(f.name),
        "city": _per_value(f.city),
        "email": _per_value(f.email),
        "username": _per_value(f.user_name),
        "phone": _per_value(f.phone_number),
        "cep": _per_value(f.postcode),
        "address": _per_value(lambda: f.address().replace("\n", ", ")),
        "cpf": _per_value(f.cpf),
        "cnpj": _per_value(f.cnpj),
        "uuid": _per_value(f.uuid4),
        "ipv4": _per_value(f.ipv4_public),
        "ipv6": _per_value(f.ipv6),
        "mac": _per_value(f.mac_address),
        "url": _per_value(f.url),
        "sentence": _per_value(f.sentence),
        "company": _per_value(f.company),
        "license_plate": _per_value(f.license_plate),
        "ean13": _per_value(f.ean13),
        "iban": _per_value(f.iban),
        "credit_card": _per_value(f.credit_card_number),
        "boolean": _per_value(f.pybool),
        "date": _per_value(f.date_object),
        "integer": _per_value(lambda: f.pyint(0, 1000)),
    }
    return Library("Faker", False, cases, getattr(faker_mod, "VERSION", ""))


def mimesis() -> Library | None:
    try:
        import mimesis as mm  # noqa: PLC0415  # pyright: ignore[reportMissingImports]
        from mimesis.locales import Locale  # noqa: PLC0415  # pyright: ignore[reportMissingImports]
    except ImportError:
        return None
    g = mm.Generic(locale=Locale.PT_BR, seed=1)
    cases: dict[str, Gen] = {
        "first_name": _per_value(g.person.first_name),
        "last_name": _per_value(g.person.last_name),
        "full_name": _per_value(g.person.full_name),
        "city": _per_value(g.address.city),
        "email": _per_value(g.person.email),
        "username": _per_value(g.person.username),
        "phone": _per_value(g.person.phone_number),
        "cep": _per_value(g.address.postal_code),
        "address": _per_value(g.address.address),
        "uuid": _per_value(g.cryptographic.uuid),
        "ipv4": _per_value(g.internet.ip_v4),
        "ipv6": _per_value(g.internet.ip_v6),
        "mac": _per_value(g.internet.mac_address),
        "url": _per_value(g.internet.url),
        "sentence": _per_value(g.text.sentence),
        "company": _per_value(g.finance.company),
        "ean13": _per_value(g.code.ean),
        "credit_card": _per_value(g.payment.credit_card_number),
        "boolean": _per_value(g.development.boolean),
        "date": _per_value(g.datetime.date),
        "integer": _per_value(lambda: g.numeric.integer_number(0, 1000)),
    }
    try:  # CPF e CNPJ ficam num provedor à parte (o lugar mudou entre versões)
        try:
            from mimesis.builtins import BrazilSpecProvider  # noqa: PLC0415  # pyright: ignore[reportMissingImports]
        except ImportError:
            from mimesis.builtins.pt_br import BrazilSpecProvider  # noqa: PLC0415  # pyright: ignore
        br = BrazilSpecProvider(seed=1)
        cases["cpf"] = _per_value(br.cpf)
        cases["cnpj"] = _per_value(br.cnpj)
    except ImportError:
        pass
    return Library("Mimesis", False, cases, getattr(mm, "__version__", ""))


def dataforge() -> Library | None:
    try:
        from dataforge import DataForge  # noqa: PLC0415  # pyright: ignore[reportMissingImports]
    except ImportError:
        return None
    fg = DataForge(locale="pt_BR", seed=1)

    def col(fn: Callable[..., Any]) -> Gen:
        return lambda n: pl.Series(fn(count=n))

    cases = {
        "first_name": col(fg.person.first_name),
        "last_name": col(fg.person.last_name),
        "full_name": col(fg.person.full_name),
        "city": col(fg.address.city),
        "email": col(fg.internet.email),
        "username": col(fg.internet.username),
        "phone": col(fg.phone.phone_number),
        "cep": col(fg.address.zip_code),
        "address": col(fg.address.full_address),
        "uuid": col(fg.misc.uuid4),
        "ipv4": col(fg.internet.ipv4),
        "ipv6": col(fg.network.ipv6),
        "mac": col(fg.network.mac_address),
        "url": col(fg.internet.url),
        "sentence": col(fg.lorem.sentence),
        "company": col(fg.company.company_name),
        "license_plate": col(fg.automotive.license_plate),
        "ean13": col(fg.barcode.ean13),
        "iban": col(fg.finance.iban),
        "credit_card": col(fg.finance.credit_card_number),
        "boolean": col(fg.misc.boolean),
        "date": col(fg.dt.date),
    }
    import importlib.metadata as md  # noqa: PLC0415

    try:
        version = md.version("dataforge-py")
    except md.PackageNotFoundError:
        version = ""
    return Library("dataforge", True, cases, version)


# ------------------------------------------------------------------ medição
@dataclass
class Result:
    ns: float | None = None  # ns por linha
    valid: float | None = None  # fração válida (None = sem regra para este gerador)
    error: str = ""


def measure(fn: Gen, n: int, repeats: int = 3) -> float:
    fn(min(n, 1_000))  # aquece (bases, caches, imports)
    best = math.inf
    for _ in range(repeats):
        gc.collect()
        t0 = time.perf_counter()
        out = fn(n)
        best = min(best, time.perf_counter() - t0)
        if len(out) != n:
            raise ValueError(f"devolveu {len(out)} valores, esperava {n}")
        del out
    return best / n * 1e9


def validity(case: str, fn: Gen, sample: int) -> float | None:
    check = CHECKS.get(case)
    if check is None:
        return None
    vals = [str(v) for v in fn(sample).to_list() if v is not None]
    return sum(map(check, vals)) / max(len(vals), 1)


def run(libs: list[Library], n: int, n_slow: int, sample: int) -> dict[str, dict[str, Result]]:
    out: dict[str, dict[str, Result]] = {}
    for case in libs[0].cases:
        out[case] = {}
        for lib in libs:
            fn = lib.cases.get(case)
            if fn is None:
                continue
            r = Result()
            try:
                r.ns = measure(fn, n if lib.vectorized else n_slow)
                r.valid = validity(case, fn, sample)
            except Exception as exc:
                r.error = f"{type(exc).__name__}: {exc}"[:80]
            out[case][lib.name] = r
        print(f"  {case}", file=sys.stderr, flush=True)
    return out


def _fmt_ns(ns: float) -> str:
    return f"{ns:,.0f}" if ns >= 100 else f"{ns:.1f}"


def table(libs: list[Library], res: dict[str, dict[str, Result]]) -> list[str]:
    names = [lib.name for lib in libs]
    cols = ["gerador", *(f"{x} (ns/linha)" for x in names), *(f"× {x}" for x in names[1:]), "válidos"]
    lines = ["| " + " | ".join(cols) + " |", "|---|" + "---:|" * (len(cols) - 2) + "---|"]
    ratios: dict[str, list[float]] = {x: [] for x in names[1:]}
    for case, row in res.items():
        base = row.get(names[0])
        cells, speed, valid = [], [], []
        for x in names:
            r = row.get(x)
            if r is None:
                cells.append("—")
            elif r.error:
                cells.append(f"erro: {r.error}")
            else:
                cells.append(_fmt_ns(r.ns or 0.0))
            valid.append("—" if r is None or r.valid is None else f"{r.valid:.0%}")
        for x in names[1:]:
            r = row.get(x)
            if base and base.ns and r and r.ns:
                ratio = r.ns / base.ns
                ratios[x].append(ratio)
                speed.append(f"{ratio:,.0f}×" if ratio >= 10 else f"{ratio:.1f}×")
            else:
                speed.append("—")
        lines.append("| " + " | ".join([case, *cells, *speed, " · ".join(valid)]) + " |")
    lines += ["", '"× biblioteca": quantas vezes o nini-datagen é mais rápido; "válidos" na ordem das colunas.', ""]
    for x, rs in ratios.items():
        if rs:
            gm = math.exp(sum(map(math.log, rs)) / len(rs))
            lines.append(f"- contra {x}: média geométrica {gm:,.1f}× ({len(rs)} geradores, de {min(rs):.1f}× a "
                         f"{max(rs):,.0f}×)")  # fmt: skip
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=1_000_000, help="linhas para as bibliotecas vetorizadas")
    ap.add_argument("--n-slow", type=int, default=50_000, help="linhas para as que geram um valor por chamada")
    ap.add_argument("--sample", type=int, default=20_000, help="amostra para conferir a validade")
    ap.add_argument("--markdown", help="também grava a tabela neste arquivo")
    args = ap.parse_args()

    libs = [lib for lib in (nini(), faker(), mimesis(), dataforge()) if lib is not None]
    import platform  # noqa: PLC0415

    head = (
        f"N = {args.n:,} (vetorizadas) e {args.n_slow:,} (valor a valor) · 1 thread · Python "
        f"{platform.python_version()} · Polars {pl.__version__} · {platform.platform()}"
    )
    versions = " · ".join(f"{lib.name} {lib.version}".strip() for lib in libs)
    missing = sorted({"Faker", "Mimesis", "dataforge"} - {lib.name for lib in libs})
    res = run(libs, args.n, args.n_slow, args.sample)
    lines = ["# nini-datagen contra outras bibliotecas", "", head, "", versions, ""]
    if missing:
        lines += [f"Não instaladas (puladas): {', '.join(missing)}.", ""]
    lines += table(libs, res)
    text = "\n".join(lines) + "\n"
    print(text)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
