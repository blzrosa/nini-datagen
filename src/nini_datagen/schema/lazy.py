"""`scan`: a tabela como fonte preguiçosa do Polars (``pl.LazyFrame``), gerada em lotes sob demanda.

Usa ``polars.io.plugins.register_io_source``: o Polars repassa as colunas pedidas (projeção), o filtro (predicado) e
o limite de linhas, e a fonte gera só o necessário:

* projeção: só as colunas pedidas e as de que elas dependem;
* limite sem filtro: só as primeiras linhas (a geração é estável por prefixo);
* filtro: aplicado lote a lote, parando quando o limite (se houver) é atingido.

Os lotes começam sempre em início de bloco, então ``scan(n, schema).collect()`` é igual a ``table(n, schema)``.
Expressões do schema rodam lote a lote: use só expressões linha a linha (sem agregações como ``mean()``).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import polars as pl

from ..providers.base import Context
from .plan import Schema, batch_rows, iter_batches

__all__ = ["scan", "scan_source"]


def scan_source(  # noqa: PLR0917 (a assinatura espelha a do Polars)
    schema: Schema,
    ctx: Context,
    n: int,
    with_columns: list[str] | None,
    predicate: pl.Expr | None,
    n_rows: int | None,
    batch_size: int | None,
) -> Iterator[pl.DataFrame]:
    """O gerador de lotes que o Polars consome (separado de `scan` para ser testável sem o Polars chamar)."""
    names = list(schema.names) if with_columns is None else list(with_columns)
    if not names:  # o Polars pediu zero colunas (ex.: só contar linhas): gera a mais barata e devolve só a altura
        names = [schema.names[0]]
    needed = set(names)
    if predicate is not None:
        needed |= set(predicate.meta.root_names())
    sub = schema.select(needed)
    limit = n if n_rows is None else max(0, min(n, n_rows))
    total = limit if predicate is None else n
    remaining = limit
    for batch in iter_batches(sub, ctx, total, batch_rows(batch_size)):
        if remaining <= 0:
            return
        df = batch.filter(predicate) if predicate is not None else batch
        df = df.select(names)
        if df.height > remaining:
            df = df.head(remaining)
        remaining -= df.height
        yield df


def scan(schema: Schema, ctx: Context, n: int, *, batch_size: int | None = None) -> pl.LazyFrame:
    """``pl.LazyFrame`` de ``n`` linhas do schema (já ligado ao locale com `Schema.bind`)."""
    out_schema = schema.run(ctx, 0).schema  # tipos de saída: uma tabela vazia custa quase nada

    def source(
        with_columns: list[str] | None, predicate: Any, n_rows: int | None, batch: int | None
    ) -> Iterator[pl.DataFrame]:
        pred = predicate if isinstance(predicate, pl.Expr) else None
        return scan_source(schema, ctx, n, with_columns, pred, n_rows, batch_size or batch)

    try:
        from polars.io.plugins import register_io_source  # noqa: PLC0415
    except ImportError:  # Polars sem fontes de IO em Python: gera tudo e devolve preguiçoso por cima
        return schema.run(ctx, n).lazy()
    return register_io_source(io_source=source, schema=out_schema)
