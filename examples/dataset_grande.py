"""100 milhões de linhas em Parquet, particionado por UF, com memória limitada (~2 lotes de 1 milhão de linhas).

uv run python examples/dataset_grande.py saida/
"""

import sys

import polars as pl

import nini_datagen as dg

path = sys.argv[1] if len(sys.argv) > 1 else "saida"
schema = dg.Schema(
    {
        "id": ("uuid", {}),
        "uf": "state",
        "valor": ("lognormal", {"mean": 5, "sigma": 1}),
        "data": ("date", {"start": "2020-01-01", "end": "2025-12-31"}),
        "obs": ("sentence", {"null_fraction": 0.7}),
    }
)
files = dg.write_parquet_dataset(path, 100_000_000, schema, seed=1, partition_by="uf", rows_per_file=2_000_000)
print(f"{len(files)} arquivos em {path}")
print(pl.scan_parquet(path, hive_partitioning=True).group_by("uf").agg(pl.len()).sort("len").collect())
