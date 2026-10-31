"""Sementes e fluxos do gerador.

Cada gerador público tem seu próprio fluxo, identificado por um nome (``"cpf"``, ``"phone"``...): com a mesma semente,
``cpf`` e ``phone`` não consomem os mesmos números (senão sairiam correlacionados). O estado inicial do fluxo vem de
``SeedSequence([seed, chave(nome)])``; o bloco ``i`` de 65.536 linhas usa esse estado avançado ``i`` vezes por
``jump()`` (2^128 passos), calculado no C++ (``dg_xoshiro_streams``).

Garantia a partir da v0.2.0: (semente, fluxo, índice do bloco) define o bloco sozinho. O resultado não depende do número
de threads e é estável por prefixo: ``n=1_000`` dá exatamente as primeiras linhas de ``n=1_000_000``.
"""

from __future__ import annotations

import hashlib

import numpy as np

from .._native import lib, ptr

__all__ = ["Seed", "block_states", "new_seed", "seed_state", "stream_key", "stream_words"]

Seed = int | None


def stream_key(stream: str) -> int:
    """Chave de 64 bits estável do nome do fluxo (blake2b; não muda entre execuções, máquinas ou versões do Python)."""
    if not stream:
        raise ValueError("o nome do fluxo não pode ser vazio")
    return int.from_bytes(hashlib.blake2b(stream.encode("utf-8"), digest_size=8).digest(), "little")


def new_seed() -> int:
    """Semente aleatória (entropia do sistema), para quando a pessoa não passa `seed`."""
    return int(np.random.SeedSequence().entropy)  # type: ignore[arg-type]


def _check_seed(seed: int | np.integer) -> int:
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise TypeError(f"seed deve ser um inteiro, não {type(seed).__name__}")
    seed = int(seed)
    if seed < 0:
        raise ValueError("seed deve ser >= 0")
    return seed


def seed_state(seed: int | np.integer, stream: str) -> np.ndarray:
    """Estado inicial (4 x uint64) do xoshiro256++ para (semente, fluxo). Nunca é todo zero."""
    ss = np.random.SeedSequence([_check_seed(seed), stream_key(stream)])
    state = ss.generate_state(4, np.uint64)
    if not state.any():  # probabilidade 2^-256, mas o xoshiro ficaria preso em zero
        state[0] = 1
    return state


def block_states(seed: int, stream: str, count: int, first: int = 0) -> np.ndarray:
    """Estados dos blocos ``first .. first+count-1`` do fluxo, como array ``(count, 4)`` de uint64 (um por linha)."""
    if count < 0 or first < 0:
        raise ValueError("count e first devem ser >= 0")
    out = np.empty((count, 4), np.uint64)
    if count:
        base = seed_state(seed, stream)
        lib().dg_xoshiro_streams(ptr(base), first, count, ptr(out))
    return out


def stream_words(seed: int | np.integer, stream: str, count: int) -> list[int]:
    """``count`` inteiros de 64 bits derivados de (semente, fluxo) por blake2b: para parâmetros sorteados uma vez por
    coluna (ex.: o passo da sequência sem repetição de ``cpf(unique=True)``). Estáveis em qualquer máquina e versão."""
    seed = _check_seed(seed)
    key = seed.to_bytes((seed.bit_length() + 8) // 8, "little") + stream.encode("utf-8")
    return [
        int.from_bytes(hashlib.blake2b(key + i.to_bytes(4, "little"), digest_size=8).digest(), "little")
        for i in range(count)
    ]
