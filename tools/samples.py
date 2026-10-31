"""samples.py -- amostras de cada gerador, para conferir a cara dos dados antes de gravar os gabaritos.

uv run python tools/samples.py               # imprime
uv run python tools/samples.py amostras.md   # também grava em Markdown
"""

from __future__ import annotations

import sys
from collections import Counter

import polars as pl

import nini_datagen as dg

N_SHOW = 12
N_STATS = 200_000


def main() -> None:
    g = dg.DataGen(seed=2026)
    out = ["# Amostras do nini-datagen", "", f"seed = {g.seed} · {dg.__version__}", ""]
    sx = g.sex(N_STATS)
    columns = {
        "integer(1..6)": g.integer(N_STATS, low=1, high=6),
        "uniform": g.uniform(N_STATS),
        "normal(10, 2)": g.normal(N_STATS, mean=10, std=2),
        "lognormal(8, 1)": g.lognormal(N_STATS, mean=8, sigma=1),
        "boolean(p=0.3)": g.boolean(N_STATS, p=0.3),
        "date": g.date(N_STATS),
        "datetime": g.datetime(N_STATS),
        "choice": g.choice(N_STATS, ["bronze", "prata", "ouro"], weights=[6, 3, 1]),
        "sex": sx,
        "age": g.age(N_STATS),
        "first_name": g.first_name(N_STATS),
        "first_name(sex=coluna)": g.first_name(N_STATS, sex=sx),
        "last_name": g.last_name(N_STATS),
        "full_name": g.full_name(N_STATS, sex=sx),
        "full_name(null_fraction=0.1)": g.full_name(N_STATS, name="full_name_nulos", null_fraction=0.1),
    }
    out += ["## Primeiras linhas", ""]
    df = pl.DataFrame({k: v.head(N_SHOW) for k, v in columns.items() if not k.startswith("first_name(")})
    with pl.Config(tbl_rows=N_SHOW, tbl_cols=-1, fmt_str_lengths=40, tbl_width_chars=400):
        out += ["```", str(df), "```", ""]
    out += ["## Resumo (200 mil linhas)", "", "| coluna | tipo | nulos | distintos | mais comuns |"]
    out.append("|---|---|---:|---:|---|")
    for k, s in columns.items():
        top = ", ".join(f"{v} ({c / len(s):.1%})" for v, c in Counter(s.to_list()).most_common(5))
        out.append(f"| {k} | {s.dtype} | {s.null_count():,} | {s.n_unique():,} | {top} |")
    fem = (sx == "F").to_numpy()
    first = columns["first_name(sex=coluna)"].to_list()

    def top_by_sex(female: bool) -> str:
        c = Counter(x for x, f in zip(first, fem, strict=True) if f == female)
        return ", ".join(f"{v} ({k:,})" for v, k in c.most_common(15))

    out += [
        "",
        "## Nomes por sexo",
        "",
        "F: " + top_by_sex(True),
        "",
        "M: " + top_by_sex(False),
        "",
        "## 30 nomes completos",
        "",
        *[f"- {x}" for x in columns["full_name"].head(30).to_list()],
    ]
    text = "\n".join(out) + "\n"
    print(text)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            fh.write(text)


if __name__ == "__main__":
    main()
