"""Compila uma gramática de frases (símbolos -> opções com {slots}) para o kernel ``dg_template_views``.

Formato de entrada: ``{símbolo: [opção, ...]}``; opção = texto (peso 1) ou ``(texto, peso)``; ``{nome}`` no texto é
trocado por uma opção sorteada do símbolo ``nome``; ``{{`` e ``}}`` são chaves literais. Não pode haver ciclos.

Tokens (uint32), tipo nos 2 bits altos: literal (00 + índice), referência a **folha** (01 + símbolo), referência
(10 + símbolo) e fim da opção (11); toda opção termina com o token de fim.
Folha é um símbolo em que toda opção é um texto sem slots (``{d}``, ``{pessoa}``, ``{canal}``...): o kernel copia o
literal sorteado direto, sem empilhar.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .tables import alias_table

__all__ = ["CompiledGrammar", "compile_grammar", "parse_option"]

REF = 0x80000000
LEAF = 0x40000000
END = 0xC0000000  # fim da opção: o kernel decodifica o tipo do token (2 bits) de uma vez só
_SLOT = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}")


def parse_option(text: str) -> list[str | tuple[str, str]]:
    """``'O {pessoa} pediu {{x}}'`` -> ``['O ', ('ref', 'pessoa'), ' pediu {x}']``."""
    out: list[str | tuple[str, str]] = []
    buf: list[str] = []
    pos = 0
    for m in _SLOT.finditer(text):
        buf.append(text[pos : m.start()])
        tok = m.group(0)
        if tok == "{{":
            buf.append("{")
        elif tok == "}}":
            buf.append("}")
        else:
            if "".join(buf):
                out.append("".join(buf))
            buf = []
            out.append(("ref", m.group(1)))
        pos = m.end()
    buf.append(text[pos:])
    if "".join(buf):
        out.append("".join(buf))
    return out


@dataclass(frozen=True, eq=False)
class CompiledGrammar:
    """Arrays do kernel + o maior e o tamanho médio (bytes) de uma frase da raiz."""

    names: tuple[str, ...]
    sym_off: np.ndarray
    opt_off: np.ndarray
    tok: np.ndarray
    tab: np.ndarray
    lit: np.ndarray
    leaf_lit: np.ndarray
    pool: np.ndarray
    row_root: bool
    max_len: int
    mean_len: float


def _split(option: Any, name: str) -> tuple[str, float]:
    text, w = option if isinstance(option, tuple) else (option, 1.0)
    if not isinstance(text, str):
        raise TypeError(f"opção inválida em {name!r}: {option!r} (use texto ou (texto, peso))")
    w = float(w)
    if not np.isfinite(w) or w < 0:
        raise ValueError(f"peso inválido em {name!r}: {w}")
    return text, w


Parsed = list[list[tuple[list[str | tuple[str, str]], float]]]  # por símbolo: [(partes da opção, peso)]


def _parse(symbols: Mapping[str, Sequence[Any]], names: list[str]) -> Parsed:
    known = set(names)
    parsed: Parsed = []
    for name in names:
        options = symbols[name]
        if isinstance(options, str) or not isinstance(options, Sequence) or len(options) == 0:
            raise ValueError(f"o símbolo {name!r} precisa de uma lista não vazia de opções")
        opts = []
        for o in options:
            text, w = _split(o, name)
            parts = parse_option(text)
            for p in parts:
                if isinstance(p, tuple) and p[1] not in known:
                    raise ValueError(f"{{{p[1]}}} usado em {name!r} não está definido")
            opts.append((parts, w))
        if sum(w for _, w in opts) <= 0:
            raise ValueError(f"o símbolo {name!r} tem todos os pesos zerados")
        parsed.append(opts)
    return parsed


MERGE_LIMIT = 1000  # maior folha combinada (opções): {d}{d}{d} cabe; tabelas maiores começam a sair do cache L1


def _merge_leaf_runs(parsed: Parsed, names: list[str]) -> None:
    """Folhas vizinhas numa opção viram uma folha só, com o produto das opções e dos pesos (``{d1}{d}{d}`` -> uma
    folha de 900 opções). A distribuição é a mesma, com menos sorteios: os 10 dígitos de um protocolo saem em 4.
    Acrescenta os símbolos combinados ao fim de ``parsed``/``names`` (no lugar)."""
    count = len(parsed)
    leaf = [all(all(isinstance(p, str) for p in parts) for parts, _ in opts) for opts in parsed]
    options = {s: [("".join(p for p in parts if isinstance(p, str)), w) for parts, w in parsed[s]]
               for s in range(count) if leaf[s]}  # fmt: skip
    index = {n: i for i, n in enumerate(names)}
    combined: dict[tuple[int, ...], str] = {}

    def symbol(run: list[int]) -> str:
        if len(run) == 1:
            return names[run[0]]
        key = tuple(run)
        if key not in combined:
            opts: list[tuple[list[str | tuple[str, str]], float]] = [([""], 1.0)]
            for s in run:
                opts = [([a[0] + text], wa * wb) for a, wa in opts for text, wb in options[s]]  # type: ignore[operator]
            combined[key] = "<" + "+".join(names[s] for s in run) + ">"
            parsed.append(opts)
            names.append(combined[key])
        return combined[key]

    for s in range(count):
        if leaf[s]:
            continue
        new_opts = []
        for parts, w in parsed[s]:
            out: list[str | tuple[str, str]] = []
            run: list[int] = []
            size = 1
            for p in [*parts, None]:
                t = index[p[1]] if isinstance(p, tuple) else -1
                if t >= 0 and leaf[t] and (not run or size * len(options[t]) <= MERGE_LIMIT):
                    run.append(t)
                    size *= len(options[t])
                    continue
                if run:
                    out.append(("ref", symbol(run)))
                run, size = [], 1
                if t >= 0 and leaf[t]:  # não coube na folha anterior: começa outra
                    run, size = [t], len(options[t])
                elif p is not None:
                    out.append(p)
            new_opts.append((out, w))
        parsed[s] = new_opts


def _encode(parsed: Parsed, sid: Mapping[str, int]) -> tuple[list[int], list[int], list[int], list[float], list[bytes]]:
    """(sym_off, opt_off, tok, pesos, literais): folhas viram um literal por opção; refs a folhas ganham o bit 30."""
    leaf = [all(all(isinstance(p, str) for p in parts) for parts, _ in opts) for opts in parsed]
    lits: dict[bytes, int] = {}

    def lit(b: bytes) -> int:
        if len(b) > 65535:
            raise ValueError("literal longo demais (máx. 65535 bytes)")
        return lits.setdefault(b, len(lits))

    sym_off, opt_off, tok, weights = [0], [0], [], []
    for s, opts in enumerate(parsed):
        for parts, w in opts:
            if leaf[s]:  # exatamente um literal por opção (o texto inteiro, mesmo vazio)
                tok.append(lit("".join(p for p in parts if isinstance(p, str)).encode("utf-8")))
            else:
                for p in parts:
                    if isinstance(p, tuple):
                        t = sid[p[1]]
                        tok.append((LEAF if leaf[t] else REF) | t)
                    else:
                        tok.append(lit(p.encode("utf-8")))
            tok.append(END)
            opt_off.append(len(tok))
            weights.append(w)
        sym_off.append(len(weights))
    return sym_off, opt_off, tok, weights, sorted(lits, key=lambda b: lits[b])


def _lengths(names: list[str], offs: tuple[list[int], list[int]], tok: list[int], w: np.ndarray,
             lit_len: np.ndarray) -> tuple[int, float]:  # fmt: skip
    """Maior e média (bytes) do texto da raiz, em ordem topológica; também detecta ciclos."""
    sym_off, opt_off = offs
    count = len(names)
    best, mean, state = [-1] * count, [0.0] * count, [0] * count

    def visit(s: int) -> None:
        if state[s] == 2:
            return
        if state[s] == 1:
            raise ValueError(f"a gramática tem ciclo envolvendo {{{names[s]}}}")
        state[s] = 1
        hi, avg = 0, 0.0
        total = w[sym_off[s] : sym_off[s + 1]].sum()
        for o in range(sym_off[s], sym_off[s + 1]):
            length, expected = 0, 0.0
            for t in tok[opt_off[o] : opt_off[o + 1] - 1]:  # sem o END
                if t & (REF | LEAF):
                    c = t & 0x3FFFFFFF
                    visit(c)
                    length += best[c]
                    expected += mean[c]
                else:
                    length += int(lit_len[t])
                    expected += int(lit_len[t])
            if w[o] > 0:
                hi = max(hi, length)
                avg += w[o] / total * expected
        best[s], mean[s], state[s] = hi, avg, 2

    for s in range(count):
        visit(s)
    return best[0], mean[0]


def compile_grammar(
    symbols: Mapping[str, Sequence[Any]], root: str = "frase", row_root: bool = False
) -> CompiledGrammar:
    """Compila ``symbols``. ``row_root``: cada opção da raiz é uma referência só (o tema), sorteada uma vez por
    linha."""
    if root not in symbols:
        raise ValueError(f"a gramática precisa do símbolo raiz {root!r}")
    names = [root] + [k for k in symbols if k != root]
    parsed = _parse(symbols, names)
    _merge_leaf_runs(parsed, names)
    sid = {k: i for i, k in enumerate(names)}
    sym_off, opt_off, tok, weights, lit_list = _encode(parsed, sid)
    if row_root:
        for o in range(sym_off[0], sym_off[1]):
            if opt_off[o + 1] - opt_off[o] != 2 or not tok[opt_off[o]] & (REF | LEAF):
                raise ValueError("com row_root, cada opção da raiz deve ser só uma referência a outro símbolo")

    lit_len = np.array([len(b) for b in lit_list] or [0], np.uint64)
    lit_off = np.zeros(max(len(lit_list), 1), np.uint64)
    pool = bytearray()
    for i, b in enumerate(lit_list):
        lit_off[i] = len(pool)
        pool += b
    lit = lit_off | (lit_len << np.uint64(32))
    # literal de cada opção de folha (as folhas têm exatamente um token por opção); 0 nas outras opções
    leaf_lit = np.zeros(max(len(opt_off) - 1, 1), np.uint64)
    for s in range(len(names)):
        if all(opt_off[o + 1] - opt_off[o] == 2 and not tok[opt_off[o]] & (REF | LEAF)
               for o in range(sym_off[s], sym_off[s + 1])):  # fmt: skip
            for o in range(sym_off[s], sym_off[s + 1]):
                leaf_lit[o] = lit[tok[opt_off[o]]]
    w = np.asarray(weights, np.float64)
    tab = np.concatenate([alias_table(w[sym_off[i] : sym_off[i + 1]]) for i in range(len(names))])
    max_len, mean_len = _lengths(names, (sym_off, opt_off), tok, w, lit_len)
    return CompiledGrammar(
        names=tuple(names),
        sym_off=np.asarray(sym_off, np.uint32),
        opt_off=np.asarray(opt_off, np.uint32),
        tok=np.asarray(tok or [0], np.uint32),
        tab=np.ascontiguousarray(tab, dtype=np.uint64),
        lit=lit,
        leaf_lit=leaf_lit,
        # folga: o kernel copia em blocos de 16 bytes
        pool=np.frombuffer(bytes(pool) + b"\0" * 32, np.uint8).copy(),
        row_root=row_root,
        max_len=max_len,
        mean_len=mean_len,
    )
