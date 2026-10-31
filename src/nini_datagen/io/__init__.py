"""Gravação de tabelas grandes em disco."""

from __future__ import annotations

from .parquet import write_parquet_dataset

__all__ = ["write_parquet_dataset"]
