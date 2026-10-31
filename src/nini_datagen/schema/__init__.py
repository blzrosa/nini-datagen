"""Tabelas: `Schema` (descrição compilada), `ref` (dependência entre colunas), `column` e `scan` (fonte preguiçosa)."""

from __future__ import annotations

from .lazy import scan, scan_source
from .plan import Schema, as_schema, batch_rows, iter_batches
from .spec import Column, ExprColumn, Ref, column, ref

__all__ = [
    "Column",
    "ExprColumn",
    "Ref",
    "Schema",
    "as_schema",
    "batch_rows",
    "column",
    "iter_batches",
    "ref",
    "scan",
    "scan_source",
]
