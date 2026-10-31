"""`write_parquet_dataset`: grava uma tabela grande em lotes (memória limitada), com partições no estilo Hive.

Os lotes são os mesmos de `scan` (alinhados aos blocos), então os arquivos juntos têm exatamente as linhas de
``table(n, schema)``, na mesma ordem, para qualquer ``batch_rows``: o tamanho do lote só muda quantos arquivos saem
(sem ``rows_per_file``) e quanta memória é usada.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote

import polars as pl

from ..providers.base import Context
from ..schema.plan import Schema, batch_rows, iter_batches

__all__ = ["HIVE_NULL", "write_parquet_dataset"]

HIVE_NULL = "__HIVE_DEFAULT_PARTITION__"
COMPRESSIONS = ("zstd", "lz4", "snappy", "gzip", "brotli", "uncompressed")


def _hive_value(v: Any) -> str:
    """Valor de partição como nome de pasta: nulo vira ``__HIVE_DEFAULT_PARTITION__``; ``/``, ``:``, ``=`` etc. viram
    ``%XX`` (o Polars, o DuckDB e o Spark decodificam; ``:`` é proibido em nomes de arquivo no Windows)."""
    return HIVE_NULL if v is None else quote(str(v), safe="-_.")


class _Sink:
    """Grava lotes: uma pasta por partição e, com ``rows_per_file``, arquivos com exatamente essa quantidade de linhas
    (o último de cada partição fica menor). Sem ``rows_per_file``, cada lote vira um arquivo por partição."""

    def __init__(self, out: Path, write: Callable[[pl.DataFrame, Path], None], cols: list[str], *, include: bool,
                 rows_per_file: int | None, max_partitions: int) -> None:  # fmt: skip
        self.out, self.write, self.cols, self.include = out, write, cols, include
        self.rpf, self.maxp = rows_per_file, max_partitions
        self.pending: dict[tuple[Any, ...], list[pl.DataFrame]] = {}
        self.count: dict[tuple[Any, ...], int] = {}
        self.files: list[Path] = []

    def _dir(self, key: tuple[Any, ...]) -> Path:
        if key not in self.count:
            if len(self.count) >= self.maxp:
                raise ValueError(
                    f"mais de {self.maxp} partições distintas em {self.cols}: use colunas de poucos valores (UF, sexo, "
                    "ano...) ou aumente max_partitions"
                )
            self.count[key] = 0
        d = self.out.joinpath(*[f"{c}={_hive_value(v)}" for c, v in zip(self.cols, key, strict=True)])
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _emit(self, key: tuple[Any, ...], df: pl.DataFrame) -> None:
        f = self._dir(key) / f"part-{self.count[key]:05d}.parquet"
        self.count[key] += 1
        self.write(df, f)
        self.files.append(f)

    def add(self, df: pl.DataFrame) -> None:
        if self.cols:
            parts = df.partition_by(self.cols, as_dict=True, include_key=self.include, maintain_order=True)
            groups = {(k if isinstance(k, tuple) else (k,)): p for k, p in parts.items()}
        else:
            groups = {(): df}
        for key, part in groups.items():
            if self.rpf is None:
                self._emit(key, part)
                continue
            self._dir(key)  # confere max_partitions já aqui
            buf = self.pending.setdefault(key, [])
            buf.append(part)
            rows = sum(p.height for p in buf)
            if rows >= self.rpf:
                whole = pl.concat(buf, rechunk=True)
                start = 0
                while whole.height - start >= self.rpf:
                    self._emit(key, whole.slice(start, self.rpf))
                    start += self.rpf
                rest = whole.slice(start)
                self.pending[key] = [rest] if rest.height else []

    def close(self) -> list[Path]:
        for key, buf in self.pending.items():
            if buf:
                self._emit(key, pl.concat(buf, rechunk=True))
        self.pending.clear()
        return self.files


def write_parquet_dataset(
    path: str | Path,
    n: int,
    schema: Schema,
    ctx: Context,
    *,
    batch_rows_: int | None = None,
    compression: str = "zstd",
    compression_level: int | None = None,
    rows_per_file: int | None = None,
    partition_by: str | Sequence[str] | None = None,
    include_partition_columns: bool = False,
    max_partitions: int = 2000,
    overlap: bool = True,
) -> list[Path]:
    """Grava ``n`` linhas do schema (já ligado ao locale) em ``path``; veja `DataGen.write_parquet_dataset`."""
    if compression not in COMPRESSIONS:
        raise ValueError(f"compression deve ser um de {', '.join(COMPRESSIONS)}")
    if rows_per_file is not None and rows_per_file < 1:
        raise ValueError("rows_per_file deve ser >= 1")
    if max_partitions < 1:
        raise ValueError("max_partitions deve ser >= 1")
    cols = [partition_by] if isinstance(partition_by, str) else list(partition_by or [])
    missing = [c for c in cols if c not in schema]
    if missing:
        raise ValueError(f"partition_by {missing} não está no schema (colunas: {', '.join(schema.names)})")
    level = 1 if compression_level is None and compression == "zstd" else compression_level

    def write(df: pl.DataFrame, f: Path) -> None:
        kw: dict[str, Any] = {"compression": compression}
        if level is not None:
            kw["compression_level"] = level
        df.write_parquet(f, **kw)

    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    sink = _Sink(out, write, cols, include=include_partition_columns, rows_per_file=rows_per_file,
                 max_partitions=max_partitions)  # fmt: skip
    batches = iter_batches(schema, ctx, n, batch_rows(batch_rows_))
    if not overlap:
        for df in batches:
            sink.add(df)
        return sink.close()
    # gera o lote seguinte enquanto grava o atual (no máximo dois lotes na memória)
    with ThreadPoolExecutor(1, thread_name_prefix="nini-datagen-io") as pool:
        nxt: Future[pl.DataFrame | None] = pool.submit(next, batches, None)
        while (df := nxt.result()) is not None:
            nxt = pool.submit(next, batches, None)
            sink.add(df)
    return sink.close()
