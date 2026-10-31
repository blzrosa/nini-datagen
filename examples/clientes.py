"""Tabela de clientes coerente: nome pelo sexo, nascimento pela idade, renda correlacionada com a idade.

uv run python examples/clientes.py
"""

import polars as pl

import nini_datagen as dg

schema = dg.Schema(
    {
        "id": ("cpf", {"unique": True, "formatted": True}),
        "sexo": "sex",
        "nome": ("full_name", {"sex": dg.ref("sexo")}),
        "idade": ("age", {"low": 18, "high": 90}),
        "nascimento": ("birthdate", {"age": dg.ref("idade"), "on": "2026-01-01"}),
        "renda": ("correlated", {"other": dg.ref("idade"), "rho": 0.4, "mean": 8, "std": 0.6, "lognormal": True}),
        "email": "email",
        "telefone": ("phone", {"style": "masked"}),
        "endereco": ("address", {"full": True}),
        "plano": dg.column("choice", ["bronze", "prata", "ouro"], weights=[6, 3, 1]),
        "cliente_desde": ("date", {"start": "2015-01-01", "end": "2026-01-01"}),
    }
)

g = dg.DataGen(seed=2026)
clientes = g.table(100_000, schema).with_columns(pl.col("endereco").struct.field("full").alias("endereco"))
print(clientes.head(10))
print(clientes.group_by("plano").agg(pl.len(), pl.col("renda").median()).sort("plano"))
