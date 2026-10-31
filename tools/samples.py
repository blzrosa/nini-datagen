"""samples.py -- amostras de cada gerador, para conferir a cara dos dados antes de gravar os gabaritos.

uv run python tools/samples.py               # imprime
uv run python tools/samples.py amostras.md   # também grava em Markdown
"""

from __future__ import annotations

import sys
from collections import Counter

import polars as pl

import nini_datagen as dg
from nini_datagen.locales import get_locale

THEMES = list(get_locale().grammar()[1])

N_SHOW = 12
N_STATS = 200_000


def address_section(g: dg.DataGen) -> list[str]:
    loc = get_locale()
    base = loc.addresses()
    out = ["", f"## Endereços (base {base.source}: {len(base):,} trechos)", ""]
    a = g.address(N_STATS, phone=True, coords=True, full=True).struct.unnest()
    with pl.Config(tbl_rows=N_SHOW, tbl_cols=-1, fmt_str_lengths=60, tbl_width_chars=400):
        out += ["```", str(a.drop("full").head(N_SHOW)), "```", ""]
    out += ["Endereço completo:", "", *[f"- {x}" for x in a["full"].head(N_SHOW).to_list()], ""]
    ufs = Counter(a["state"].to_list())
    out.append("UFs: " + ", ".join(f"{u} ({c / len(a):.1%})" for u, c in ufs.most_common(10)))
    nums = a["number"]
    with_complement = 1 - a["complement"].null_count() / len(a)
    out.append(f"Número: mediana {nums.median():.0f}, máximo {nums.max()}; complemento em {with_complement:.1%}")
    out += ["", "CEP (só SP): " + " · ".join(f"`{x}`" for x in g.cep(8, uf="SP").to_list())]
    cities = Counter(g.city(N_STATS).to_list()).most_common(10)
    out += ["", "Cidades (pela população): " + ", ".join(f"{c} ({k / N_STATS:.1%})" for c, k in cities)]
    states = Counter(g.state(N_STATS).to_list()).most_common(6)
    out += ["", "UFs (pela população): " + ", ".join(f"{u} ({k / N_STATS:.1%})" for u, k in states), ""]
    return out


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
    docs = {
        "cpf": g.cpf(N_STATS),
        "cpf(formatted, unique)": g.cpf(N_STATS, name="cpf_u", formatted=True, unique=True),
        "cnpj(formatted)": g.cnpj(N_STATS, formatted=True),
        "cnpj(alphanumeric, formatted)": g.cnpj(N_STATS, name="cnpj_a", alphanumeric=True, formatted=True),
        "cnpj(branch=None)": g.cnpj(N_STATS, name="cnpj_b", branch=None),
        "pis(formatted)": g.pis(N_STATS, formatted=True),
        "voter_id(formatted)": g.voter_id(N_STATS, formatted=True),
        "cnh": g.cnh(N_STATS),
        "rg(formatted)": g.rg(N_STATS, formatted=True),
        "license_plate": g.license_plate(N_STATS),
        "license_plate(old)": g.license_plate(N_STATS, name="placa_antiga", style="old"),
        "credit_card(formatted)": g.credit_card(N_STATS, formatted=True),
        "iban": g.iban(N_STATS),
        "ean13": g.ean13(N_STATS),
        "uuid": g.uuid(N_STATS),
        "ipv4": g.ipv4(N_STATS),
        "ipv4(private)": g.ipv4(N_STATS, name="ipv4_priv", private=True),
        "ipv6": g.ipv6(N_STATS),
        "mac": g.mac(N_STATS),
        "url": g.url(N_STATS),
        "phone": g.phone(N_STATS),
        "phone(masked, uf=SP)": g.phone(N_STATS, name="phone_sp", style="masked", uf="SP"),
        "email": g.email(N_STATS),
        "username": g.username(N_STATS),
        "company": g.company(N_STATS),
        "occupation": g.occupation(N_STATS),
    }
    texts = {
        "sentence": g.sentence(N_STATS),
        **{f"sentence(theme={t})": g.sentence(N_STATS, name=f"sentence_{t}", theme=t) for t in THEMES},
        "paragraph": g.paragraph(N_STATS),
    }
    vehicle = g.vehicle(N_STATS)
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
    out += ["", "## Documentos e rede", ""]
    for k, s in docs.items():
        out.append(f"**{k}** ({s.n_unique():,} distintos em {len(s):,}): " + " · ".join(f"`{x}`" for x in s.head(6)))
        out.append("")
    out += ["## Frases (6 de cada)", ""]
    for k, s in texts.items():
        out += [f"**{k}** ({s.n_unique():,} distintas em {len(s):,})", "", *[f"- {x}" for x in s.head(6)], ""]
    v = vehicle.struct.unnest()
    out += ["## Veículos", "", "```", str(v.head(N_SHOW)), "```", ""]
    brands = Counter(v["brand"].to_list()).most_common()
    out.append("Marcas: " + ", ".join(f"{b} ({c / len(v):.1%})" for b, c in brands))
    out += address_section(g)
    text = "\n".join(out) + "\n"
    print(text)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as fh:
            fh.write(text)


if __name__ == "__main__":
    main()
