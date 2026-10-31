"""Interface dos geradores (Strategy) e o roteiro comum de geração (Template Method).

Cada provider sabe **planejar** uma geração (`Provider.plan`): aloca os buffers da coluna inteira e devolve um `Job`. O
roteiro em `Provider.generate` é sempre o mesmo:

1. divide ``n`` em blocos fixos de `BLOCK_ROWS` linhas (`core.blocks`);
2. calcula o estado do gerador de cada bloco a partir de (seed, fluxo, índice do bloco) (`core.rng`);
3. preenche cada bloco (`Job.fill`) — em paralelo quando o gerador é caro o bastante —, cada um na sua fatia dos
   buffers, e os bits de nulos num fluxo próprio;
4. entrega os buffers ao Polars sem copiar (`Job.finish`).

Como ``BLOCK_ROWS`` é múltiplo de 64, cada bloco também cai em palavras inteiras dos bits de booleanos e de nulos.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Generic, TypeVar

import numpy as np
import polars as pl

from .._native import lib, ptr
from ..config.base import BaseConfig
from ..core.arrow import primitive_to_series
from ..core.blocks import Block, map_blocks, split
from ..core.rng import block_states
from ..core.views import trim
from ..locales import Locale

__all__ = [
    "ArrayJob",
    "BitsJob",
    "Context",
    "Job",
    "Prepared",
    "Provider",
    "Run",
    "TextJob",
    "probability_threshold",
    "validity_bits",
]

C = TypeVar("C", bound=BaseConfig)

# Geradores mais baratos que isto (ns por linha) rodam numa thread só: o custo de despachar um bloco de 65.536
# linhas para outra thread (~50-100 µs) não se paga e, nos baratíssimos (booleano), deixa tudo mais lento.
PARALLEL_MIN_NS = 2.0


@dataclass(frozen=True)
class Context:
    """O que vale para uma geração inteira: semente, locale e número de threads (None = automático)."""

    seed: int
    locale: Locale
    threads: int | None = None


@dataclass(frozen=True)
class Run:
    """Uma geração de uma coluna: o `Context`, o nome da coluna (que é também o fluxo) e os blocos.

    ``first_block``: bloco da coluna em que esta geração começa (0 = desde a primeira linha). Os estados do gerador
    são sempre os da coluna inteira, então gerar em lotes dá exatamente o mesmo que gerar tudo de uma vez.
    """

    ctx: Context
    name: str
    n: int
    blocks: list[Block]
    first_block: int = 0

    @property
    def locale(self) -> Locale:
        return self.ctx.locale

    def states(self, suffix: str = "") -> np.ndarray:
        """Estados do gerador por bloco, ``(len(blocks), 4)``, do fluxo ``name + suffix`` (sufixo = fluxo auxiliar)."""
        return self.stream_states(self.name + suffix)

    def stream_states(self, stream: str) -> np.ndarray:
        """Estados por bloco de um fluxo com nome qualquer (providers compostos), alinhados a esta geração."""
        return block_states(self.ctx.seed, stream, len(self.blocks), self.first_block)

    def bits(self, p: float, suffix: str) -> np.ndarray:
        """Bits Bernoulli(p) para as ``n`` linhas, num fluxo auxiliar (bloco a bloco, como os dados)."""
        out = np.empty(-(-self.n // 64), np.uint64)
        st = self.states(suffix)
        thr = probability_threshold(p)
        fn = lib().dg_bool_bits
        for b in self.blocks:
            fn(ptr(st[b.index]), thr, b.rows, ptr(out[b.start // 64 :]))
        return out


@dataclass
class Prepared:
    """Uma coluna planejada: preencha cada bloco com `fill` (em qualquer ordem, em paralelo) e monte com `finish`."""

    run: Run
    job: Job
    states: np.ndarray
    validity: np.ndarray | None
    null_states: np.ndarray | None
    threshold: int

    def fill(self, b: Block) -> None:
        self.job.fill(b, self.states[b.index])
        if self.validity is not None and self.null_states is not None:
            lib().dg_bool_bits(ptr(self.null_states[b.index]), self.threshold, b.rows,
                               ptr(self.validity[b.start // 64 :]))  # fmt: skip

    def finish(self) -> pl.Series:
        return self.job.finish(self.run.name, self.validity)


class Job(ABC):
    """Uma geração em andamento: buffers da coluna inteira, preenchidos bloco a bloco."""

    @abstractmethod
    def fill(self, block: Block, state: np.ndarray) -> None:
        """Preenche as linhas do bloco. Roda em paralelo com outros blocos: só escreve na fatia do bloco."""

    @abstractmethod
    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        """Monta a Series (sem copiar os buffers). ``validity``: bits de presença (1 = valor, 0 = nulo) ou None."""


def probability_threshold(p: float) -> int:
    """Probabilidade -> limiar em escala 2^32 do kernel de bits (0 = nunca, 2^32 = sempre)."""
    return round(p * 2**32)


def validity_bits(n: int, null_fraction: float) -> np.ndarray | None:
    """Buffer (vazio) dos bits de presença para ``n`` linhas, ou None se não há nulos."""
    if null_fraction <= 0.0:
        return None
    return np.empty(-(-n // 64), np.uint64)


class Provider(ABC, Generic[C]):
    """Um gerador. Subclasses definem ``kind`` (nome no registry), ``config_cls`` e `plan`.

    ``inputs``: nomes de argumentos que recebem dados em vez de configuração (ex. a coluna ``sex`` de ``first_name``).
    ``positional``: campo da configuração que pode vir como segundo argumento posicional (ex. ``values`` de ``choice``).
    ``ns_per_row``: custo aproximado, usado só para decidir se vale paralelizar.
    """

    kind: ClassVar[str]
    config_cls: ClassVar[type[BaseConfig]]
    inputs: ClassVar[tuple[str, ...]] = ()
    positional: ClassVar[str | None] = None
    ns_per_row: ClassVar[float] = 5.0

    # ------------------------------------------------------------------ para as subclasses
    @abstractmethod
    def plan(self, run: Run, config: C, inputs: Mapping[str, Any]) -> Job:
        """Aloca os buffers da coluna inteira e prepara o que é compartilhado entre os blocos."""

    def take_inputs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Separa dos kwargs os que são dados (``inputs``); o resto vira configuração."""
        return {k: kwargs.pop(k) for k in self.inputs if k in kwargs}

    # ------------------------------------------------------------------ roteiro comum
    def column_name(self, config: C) -> str:
        return config.name or self.kind

    def start(self, n: int, config: C, ctx: Context, first_block: int = 0) -> Run:
        return Run(ctx, self.column_name(config), n, split(n, first_block), first_block)

    def prepare(
        self, n: int, config: C, ctx: Context, inputs: Mapping[str, Any] | None = None, first_block: int = 0
    ) -> Prepared:
        """Planeja a coluna sem preencher: quem chama roda `Prepared.fill` em cada bloco e depois `Prepared.finish`.

        É o que as tabelas usam para preencher todas as colunas de um bloco de uma vez (paralelismo por bloco).
        """
        run = self.start(n, config, ctx, first_block)
        job = self.plan(run, config, inputs or {})
        validity = validity_bits(n, config.null_fraction)
        null_states = run.states(":null") if validity is not None else None
        return Prepared(
            run, job, run.states(), validity, null_states, probability_threshold(1.0 - config.null_fraction)
        )

    def generate(
        self, n: int, config: C, ctx: Context, inputs: Mapping[str, Any] | None = None, first_block: int = 0
    ) -> pl.Series:
        prep = self.prepare(n, config, ctx, inputs, first_block)
        threads = 1 if self.ns_per_row < PARALLEL_MIN_NS else ctx.threads
        map_blocks(prep.fill, prep.run.blocks, threads)
        return prep.finish()

    def moments(self, config: C, locale: Locale) -> tuple[float, float] | None:
        """Média e desvio padrão da distribuição gerada, quando conhecidos (usados por ``correlated`` numa tabela)."""
        return None

    @property
    def composite(self) -> bool:
        """True se o provider monta a coluna sozinho (sobrescreve `generate`) e não pode ser preparado por bloco."""
        return type(self).generate is not Provider.generate

    def validity(self, run: Run, config: C) -> np.ndarray | None:
        """Bits de presença (mesmo fluxo ``:null`` do roteiro comum), para providers compostos."""
        if config.null_fraction <= 0.0:
            return None
        return run.bits(1.0 - config.null_fraction, ":null")


# ---------------------------------------------------------------------------- jobs reaproveitáveis
Kernel = Callable[[int, int, int], None]  # (ponteiro do estado, linhas, ponteiro da saída)


class ArrayJob(Job):
    """Um valor primitivo por linha num array numpy (inteiros, reais, datas): ``kernel(estado, m, saída)`` por bloco.

    ``post``: ajuste no lugar da fatia do bloco depois do kernel (ex.: índice -> idade). ``typ``: tipo Arrow lógico.
    """

    def __init__(self, n: int, dtype: Any, kernel: Kernel, *, post: Callable[[np.ndarray], None] | None = None,
                 typ: Any = None) -> None:  # fmt: skip
        self.out = np.empty(n, dtype)
        self.kernel = kernel
        self.post = post
        self.typ = typ

    def fill(self, block: Block, state: np.ndarray) -> None:
        seg = self.out[block.start : block.start + block.rows]
        self.kernel(ptr(state), block.rows, ptr(seg))
        if self.post is not None:
            self.post(seg)

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        return primitive_to_series(self.out, name, validity, self.typ)


# (ponteiro do estado, linhas, ponteiro das views, ponteiro do texto, primeira linha global do bloco)
TextKernel = Callable[[int, int, int, int, int], None]


class TextJob(Job):
    """Texto que o kernel escreve sozinho: views da coluna inteira + um buffer de texto por bloco.

    ``stride``: bytes reservados por linha no buffer do bloco (o kernel escreve o texto longo da linha ``r`` em
    ``r * stride`` e aponta a view para lá); 0 quando o texto sempre cabe na view (até 12 bytes) e não há buffer.
    O kernel recebe também a primeira linha global do bloco (usada pelas sequências sem repetição).
    Os kernels marcam o buffer 0; aqui cada bloco passa a apontar para o seu (índice de buffer = índice do bloco).
    """

    _DUMMY = np.zeros(64, np.uint8)

    def __init__(self, n: int, stride: int, kernel: TextKernel, n_blocks: int, *, packed: bool = False,
                 slack: int = 0) -> None:  # fmt: skip
        self.views = np.empty((n, 4), np.uint32)
        self.stride = stride
        self.kernel = kernel
        self.packed = packed  # o kernel escreve os textos em sequência (stride = limite por linha): apara no fim
        self.slack = slack  # bytes extras no fim do buffer (kernels que copiam blocos fixos além do texto)
        self.datas: list[np.ndarray] = [np.empty(0, np.uint8)] * n_blocks

    def fill(self, block: Block, state: np.ndarray) -> None:
        seg = self.views[block.start : block.start + block.rows]
        data = np.empty(block.rows * self.stride + self.slack, np.uint8) if self.stride else self._DUMMY
        self.kernel(ptr(state), block.rows, ptr(seg), ptr(data), block.row0)
        if self.stride:
            # uma passada no C++: aponta as views longas para o buffer deste bloco e mede os bytes usados
            used = lib().dg_views_used(ptr(seg), block.rows, block.index)
            self.datas[block.index] = trim(data, used) if self.packed or self.slack else data

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        from ..core.arrow import views_to_series  # noqa: PLC0415

        return views_to_series(self.views, self.datas if self.stride else None, name, validity)


class BitsJob(Job):
    """Booleanos: bits empacotados (64 linhas por palavra), escritos direto pelo kernel."""

    def __init__(self, n: int, threshold: int) -> None:
        self.n = n
        self.bits = np.empty(-(-n // 64), np.uint64)
        self.threshold = threshold

    def fill(self, block: Block, state: np.ndarray) -> None:
        lib().dg_bool_bits(ptr(state), self.threshold, block.rows, ptr(self.bits[block.start // 64 :]))

    def finish(self, name: str, validity: np.ndarray | None) -> pl.Series:
        from ..core.arrow import bits_to_series  # noqa: PLC0415

        return bits_to_series(self.bits, self.n, name, validity)
