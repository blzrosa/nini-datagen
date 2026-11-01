"""Frases e parágrafos por gramática (`core.grammar` + kernel ``dg_template_views``).

O texto de uma linha pode ir de poucos bytes a ~1,5 KB (parágrafo longo); reservar o máximo para as 65.536 linhas do
bloco daria ~100 MB. O job reserva a média estimada (+15%) e, se o buffer encher, o kernel para antes da linha que não
caberia; o job abre outro buffer e continua com o mesmo estado do gerador (atualizado no lugar pelo kernel). O resultado
não depende de onde o buffer foi cortado.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import polars as pl

from .._native import lib, ptr
from ..config.text import ParagraphConfig, SentenceConfig
from ..core.arrow import views_to_series
from ..core.blocks import Block
from ..core.grammar import CompiledGrammar, compile_grammar, parse_option
from ..core.memory import empty
from ..core.views import trim
from ..locales import Grammar, Locale
from ..registry import registry
from .base import Job, Provider, Run

__all__ = ["GrammarJob", "grammar_for"]

_SLACK = 64  # o kernel copia em blocos de 32/16 bytes: pode escrever até 31 além do fim do texto


def _rename(option: Any, mapping: Mapping[str, str]) -> Any:
    """Troca os nomes dos slots de uma opção (``{pessoa}`` -> ``{saude__pessoa}``), mantendo o peso."""
    text, w = option if isinstance(option, tuple) else (option, None)
    parts = []
    for p in parse_option(text):
        if isinstance(p, tuple):
            parts.append("{" + mapping.get(p[1], p[1]) + "}")
        else:
            parts.append(p.replace("{", "{{").replace("}", "}}"))
    s = "".join(parts)
    return s if w is None else (s, w)


def _theme_symbols(common: Grammar, themes: Mapping[str, Grammar], theme: str) -> tuple[Grammar, bool]:
    if theme == "geral":  # todos os temas, com prefixo para os nomes não colidirem; o tema é sorteado por linha
        sym = dict(common)
        roots = []
        for t, d in themes.items():
            local = {k: f"{t}__{k}" for k in d}
            for k, opts in d.items():
                sym[f"{t}__{k}"] = [_rename(o, local) for o in opts]
            roots.append("{" + f"{t}__frase" + "}")
        sym["frase"] = roots
        return sym, True
    if theme not in themes:
        raise ValueError(f"tema desconhecido: {theme!r}; use um de {sorted(themes)} ou 'geral'")
    return {**common, **themes[theme]}, False


def grammar_for(locale: Locale, config: SentenceConfig) -> CompiledGrammar:
    """Gramática compilada para a configuração (em cache no locale)."""
    key = ("grammar", config.theme, config.templates, config.slots)

    def build() -> CompiledGrammar:
        common, themes = locale.grammar()
        if config.templates is None and config.slots is None:
            sym, row_root = _theme_symbols(common, themes, config.theme)
            return compile_grammar(sym, row_root=row_root)
        sym = dict(common)
        sym.update({k: list(v) for k, v in (config.slots or ())})
        if config.templates is not None:
            sym["frase"] = list(config.templates)
        return compile_grammar(sym)

    return locale.cached(key, build)


class GrammarJob(Job):
    """Views da coluna inteira + um ou mais buffers de texto por bloco (veja o docstring do módulo)."""

    def __init__(self, n: int, g: CompiledGrammar, smin: int, smax: int, n_blocks: int) -> None:
        self.views = empty((n, 4), np.uint32)
        self.g, self.smin, self.smax = g, smin, smax
        self.max_row = smax * (g.max_len + 1)
        self.mean_row = (smin + smax) / 2 * (g.mean_len + 1)
        # por bloco: [(primeira linha no bloco, linhas, buffer), ...]
        self.parts: list[list[tuple[int, int, np.ndarray]]] = [[] for _ in range(n_blocks)]

    def fill(self, block: Block, state: np.ndarray) -> None:
        g, fn = self.g, lib().dg_template_views
        done, parts = 0, []
        while done < block.rows:
            left = block.rows - done
            cap = max(int(left * self.mean_row * 1.15) + 4096, self.max_row)
            data = empty(cap + _SLACK, np.uint8)
            k = fn(
                ptr(state), ptr(g.sym_off), ptr(g.tab), ptr(g.opt_off), ptr(g.tok), ptr(g.lit), ptr(g.leaf_lit),
                ptr(g.pool), self.smin, self.smax, int(g.row_root), self.max_row, cap, left,
                ptr(self.views[block.start + done :]), ptr(data),
            )  # fmt: skip
            parts.append((done, k, data))
            done += k
        self.parts[block.index] = parts

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        # índice global de cada buffer, na ordem dos blocos: aponta as views longas e apara o que sobrou
        datas: list[np.ndarray] = []
        start = 0
        set_buffer = lib().dg_views_used
        for parts in self.parts:
            for first, k, data in parts:
                seg = self.views[start + first : start + first + k]
                used = set_buffer(ptr(seg), k, len(datas))
                datas.append(trim(data, used))
            start += sum(k for _, k, _ in parts)
        return views_to_series(self.views, datas or None, name, validity)


@registry.register
class SentenceProvider(Provider[SentenceConfig]):
    kind = "sentence"
    config_cls = SentenceConfig
    ns_per_row = 60.0

    def plan(self, run: Run, config: SentenceConfig, inputs: Mapping[str, Any]) -> Job:
        smin, smax = config.sentence_range
        return GrammarJob(run.n, grammar_for(run.locale, config), smin, smax, len(run.blocks))


@registry.register
class ParagraphProvider(SentenceProvider):
    kind = "paragraph"
    config_cls = ParagraphConfig
    ns_per_row = 250.0
