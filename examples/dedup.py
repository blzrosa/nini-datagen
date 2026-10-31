"""Base suja com duplicatas e gabarito, para testar deduplicação e fuzzy matching.

uv run python examples/dedup.py
"""

import polars as pl

import nini_datagen as dg

schema = dg.Schema(
    {
        "nome": ("full_name", {"dirty": {"case": 0.02, "accents": 0.05, "whitespace": 0.02}}),
        "cpf": ("cpf", {"formatted": True, "dirty": {"unmask": 0.3, "null_like": 0.01}}),
        "cidade": ("city", {"with_state": True}),
        "nascimento": ("date", {"start": "1950-01-01", "end": "2007-12-31", "null_fraction": 0.03}),
    }
)

g = dg.DataGen(seed=7)
base = g.add_duplicates(
    g.table(50_000, schema),
    0.05,
    dirty={"nome": {"typo": 0.5, "truncate": 0.05}, "cpf": {"unmask": 0.5, "typo": 0.05}},
)
pares = base.filter(pl.col("dup_of").is_not_null()).select("row_id", "dup_of")
print(f"{base.height:,} linhas, {pares.height:,} duplicatas (o gabarito são os pares row_id -> dup_of)")
print(base.filter(pl.col("dup_of").is_not_null()).head(10))
