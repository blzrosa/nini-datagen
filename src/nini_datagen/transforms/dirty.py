"""Dados sujos: aplica os defeitos de `DirtyConfig` a uma coluna.

Cada defeito tem dois fluxos do gerador, alinhados aos blocos da coluna como os dados: ``<coluna>:dirty.<defeito>``
(um sorteio por linha decide se a linha é afetada) e ``<coluna>:dirty.<defeito>.arg`` (um inteiro por linha com os
parâmetros: posição do erro, letra, variante). Por isso a coluna suja também é estável por prefixo e sai igual
gerada inteira ou em lotes (`scan`, `write_parquet_dataset`), e mudar a fração de um defeito não muda os outros.

As transformações de texto são do Polars (``str.slice``, ``replace_many``...) e só rodam nas linhas sorteadas.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import polars as pl

from .._native import lib, ptr
from ..config.dirty import DirtyConfig
from ..core.blocks import Block, split
from ..core.memory import empty
from ..core.rng import block_states

__all__ = ["RowStreams", "apply_dirty", "dirty"]

_ACC_FROM = list("áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇñÑ")
_ACC_TO = list("aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUCnN")
_LETTERS = "abcdefghijklmnopqrstuvwxyz"
_ARG_SPAN = 1 << 62


@dataclass(frozen=True)
class RowStreams:
    """De onde vêm os sorteios por linha: semente, prefixo do fluxo e os blocos (com o bloco inicial da coluna)."""

    seed: int
    prefix: str
    blocks: list[Block]
    first_block: int
    n: int

    def uniform(self, stream: str) -> np.ndarray:
        out = empty(self.n, np.float64)
        st = block_states(self.seed, self.prefix + stream, len(self.blocks), self.first_block)
        fn = lib().dg_rand_f64
        for b in self.blocks:
            fn(ptr(st[b.index]), 0.0, 1.0, b.rows, ptr(out[b.start :]))
        return out

    def integers(self, stream: str, span: int = _ARG_SPAN) -> np.ndarray:
        """Um inteiro uniforme em ``[0, span)`` por linha (padrão: ``[0, 2^62)``)."""
        out = empty(self.n, np.int64)
        st = block_states(self.seed, self.prefix + stream, len(self.blocks), self.first_block)
        fn = lib().dg_rand_i64
        for b in self.blocks:
            fn(ptr(st[b.index]), 0, span, b.rows, ptr(out[b.start :]))
        return out

    def rows(self, stream: str, p: float) -> tuple[np.ndarray, np.ndarray]:
        """Linhas sorteadas com probabilidade ``p`` e o inteiro de parâmetros de cada uma."""
        idx = np.flatnonzero(self.uniform(stream) < p)
        return idx, self.integers(stream + ".arg")[idx]


def _put(s: pl.Series, idx: np.ndarray, new: pl.Series) -> pl.Series:
    """Cópia de ``s`` com ``s[idx] = new`` (``new`` tem ``len(idx)`` valores)."""
    if len(idx) == 0:
        return s
    pos = np.full(len(s), -1, np.int64)
    pos[idx] = np.arange(len(idx))
    hit = pos >= 0
    spread = new.cast(s.dtype).gather(pl.Series(np.where(hit, pos, 0)))
    return spread.zip_with(pl.Series(hit), s).alias(s.name)


def _variant(arg: np.ndarray, k: int) -> np.ndarray:
    return (arg % k).astype(np.int64)


def _typo(sub: pl.Series, arg: np.ndarray) -> pl.Series:
    """Apaga, troca com a vizinha, repete ou substitui o caractere numa posição sorteada."""
    n_chars = sub.str.len_chars().fill_null(0).to_numpy()
    pos = ((arg >> 8) % np.maximum(n_chars - 1, 1)).astype(np.int64)
    letters = np.array(list(_LETTERS))[(arg >> 40) % len(_LETTERS)]
    x, p = pl.col("x"), pl.col("p")
    frame = pl.DataFrame({"x": sub, "p": pos, "l": letters, "k": _variant(arg, 4)})
    out = frame.select(
        pl.when(pl.col("k") == 0)
        .then(pl.concat_str([x.str.slice(0, p), x.str.slice(p + 1)]))
        .when(pl.col("k") == 1)
        .then(pl.concat_str([x.str.slice(0, p), x.str.slice(p + 1, 1), x.str.slice(p, 1), x.str.slice(p + 2)]))
        .when(pl.col("k") == 2)
        .then(pl.concat_str([x.str.slice(0, p + 1), x.str.slice(p)]))
        .otherwise(pl.concat_str([x.str.slice(0, p), pl.col("l"), x.str.slice(p + 1)]))
        .alias("x")
    )
    return out.to_series()


def _truncate(sub: pl.Series, arg: np.ndarray) -> pl.Series:
    n_chars = sub.str.len_chars().fill_null(0).to_numpy()
    keep = 1 + (arg % np.maximum(n_chars - 1, 1))  # 1 .. len-1 caracteres (sempre corta, sobra pelo menos 1)
    frame = pl.DataFrame({"x": sub, "k": keep.astype(np.int64)})
    return frame.select(pl.col("x").str.slice(0, pl.col("k"))).to_series()


def _case(sub: pl.Series, arg: np.ndarray) -> pl.Series:
    frame = pl.DataFrame({"x": sub, "k": _variant(arg, 2)})
    x = pl.col("x")
    upper_or_lower = pl.when(pl.col("k") == 0).then(x.str.to_uppercase()).otherwise(x.str.to_lowercase())
    return frame.select(upper_or_lower).to_series()


def _whitespace(sub: pl.Series, arg: np.ndarray) -> pl.Series:
    frame = pl.DataFrame({"x": sub, "k": _variant(arg, 3)})
    x = pl.col("x")
    return frame.select(
        pl.when(pl.col("k") == 0)
        .then(pl.concat_str([pl.lit(" "), x]))
        .when(pl.col("k") == 1)
        .then(pl.concat_str([x, pl.lit(" ")]))
        .otherwise(pl.concat_str([pl.lit("  "), x, pl.lit(" ")]))
    ).to_series()


def _mojibake(sub: pl.Series, arg: np.ndarray) -> pl.Series:
    vals = [None if v is None else v.encode("utf-8").decode("latin-1") for v in sub.to_list()]
    return pl.Series(sub.name, vals, dtype=pl.String)


def _accents(sub: pl.Series, arg: np.ndarray) -> pl.Series:
    return sub.str.replace_many(_ACC_FROM, _ACC_TO)


def _unmask(sub: pl.Series, arg: np.ndarray) -> pl.Series:
    return sub.str.replace_all(r"[.\-/()\s]", "")  # só a pontuação de máscara: letras acentuadas ficam


_TEXT: dict[str, Callable[[pl.Series, np.ndarray], pl.Series]] = {
    "accents": _accents,
    "mojibake": _mojibake,
    "unmask": _unmask,
    "typo": _typo,
    "truncate": _truncate,
    "case": _case,
    "whitespace": _whitespace,
}


def apply_dirty(s: pl.Series, config: DirtyConfig, rows: RowStreams) -> pl.Series:
    """A coluna com os defeitos de ``config`` (veja `DirtyConfig`); ``rows`` dá os sorteios por linha."""
    if config.is_empty:
        return s
    if config.text_ops and s.dtype != pl.String:
        ops = ", ".join(op for op, _ in config.text_ops)
        raise ValueError(f"coluna {s.name!r} ({s.dtype}): {ops} só valem para texto")
    for op, p in config.text_ops:
        idx, arg = rows.rows(f":dirty.{op}", p)
        if not len(idx):
            continue
        if op == "null_like":
            tokens = pl.Series(list(config.null_tokens), dtype=pl.String)
            s = _put(s, idx, tokens.gather(pl.Series(arg % len(tokens))))
        else:
            s = _put(s, idx, _TEXT[op](s.gather(pl.Series(idx)), arg))
    if config.outliers > 0:
        if not s.dtype.is_numeric():
            raise ValueError(f"coluna {s.name!r} ({s.dtype}): outliers só vale para números")
        idx, arg = rows.rows(":dirty.outliers", config.outliers)
        if len(idx):
            factors = np.asarray(config.outlier_factors, np.float64)[arg % len(config.outlier_factors)]
            new = (s.gather(pl.Series(idx)).cast(pl.Float64) * pl.Series(factors)).cast(s.dtype, strict=False)
            s = _put(s, idx, new)
    for i, (value, frac) in enumerate(config.sentinel):
        if frac <= 0:
            continue
        idx, _ = rows.rows(f":dirty.sentinel{i}", frac)
        if len(idx):
            s = _put(s, idx, pl.Series([value] * len(idx)).cast(s.dtype))
    return s


def dirty(s: pl.Series, config: DirtyConfig | None = None, /, *, seed: int = 0, **kwargs: object) -> pl.Series:
    """Suja uma coluna qualquer: ``dg.dirty(df["nome"], typo=0.02, case=0.01, seed=7)`` (veja `DirtyConfig`).

    O resultado depende de (``seed``, nome da coluna, configuração); colunas geradas já aceitam ``dirty=`` direto.
    """
    cfg = DirtyConfig.model_validate({**(config.model_dump() if config else {}), **kwargs})
    rows = RowStreams(seed, s.name or "coluna", split(len(s)), 0, len(s))
    return apply_dirty(s, cfg, rows)
