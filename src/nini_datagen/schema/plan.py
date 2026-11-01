"""`Schema`: a descrição de uma tabela, validada e compilada uma vez, e a execução dela por blocos de linhas.

Compilar = ler cada coluna (`spec.parse`), validar a configuração, achar as dependências (``ref`` e expressões) e
ordenar as colunas em níveis: um nível só depende dos anteriores. Executar = para cada nível, planejar todas as
colunas de gerador (`Provider.prepare`) e preencher **bloco a bloco, todas as colunas do bloco de uma vez**, com os
blocos em paralelo. Assim até as colunas baratas (inteiros, booleanos) entram no paralelismo, porque o trabalho de
um bloco é a soma das colunas.

Reprodutibilidade: cada coluna depende só de (semente, nome da coluna, configuração, colunas de que depende), então
``table(n, schema)[c]`` é exatamente ``generate(tipo, n, name=c, ...)``, para qualquer número de threads, e gerar em
lotes (`scan`, `write_parquet_dataset`) dá a mesma tabela que gerar tudo de uma vez.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

import polars as pl

from ..core.blocks import BLOCK_ROWS, Block, parallel_map, resolve_threads, split
from ..locales import Locale
from ..providers.base import PARALLEL_MIN_NS, Context, Prepared
from ..registry import registry
from .spec import Column, ExprColumn, Spec, parse

__all__ = ["Schema", "as_schema"]

# correlated: parâmetros que vêm da distribuição da coluna referida quando não são dados
_MOMENT_KINDS = {"correlated": ("other", "center", "scale")}


class Schema:
    """Descrição de uma tabela: ``{nome: coluna}``, validada e compilada uma vez (reaproveite entre chamadas).

    >>> schema = dg.Schema({
    ...     "id": ("cpf", {"unique": True, "formatted": True}),
    ...     "sexo": "sex",
    ...     "nome": ("full_name", {"sex": dg.ref("sexo")}),      # nome coerente com o sexo
    ...     "idade": ("age", {"low": 18, "high": 90}),
    ...     "nascimento": ("birthdate", {"age": dg.ref("idade"), "on": "2026-01-01"}),
    ...     "renda": ("correlated", {"other": dg.ref("idade"), "rho": 0.4, "mean": 8, "std": 0.6, "lognormal": True}),
    ...     "uf": "state",
    ...     "meses": pl.col("idade") * 12,                        # expressão do Polars sobre outras colunas
    ... })
    >>> g.table(1_000_000, schema)                               # doctest: +SKIP

    Cada coluna pode ser ``"tipo"``, ``("tipo", {parâmetros})``, ``("tipo", Config(...))``, uma configuração
    (``dg.CPFConfig(formatted=True)``), ``dg.column("tipo", ...)`` ou uma expressão do Polars. Os parâmetros são os
    mesmos de `DataGen.generate` (inclusive ``null_fraction``); o nome da coluna é a chave do dict.
    """

    __slots__ = ("_columns", "_levels", "_order")

    def __init__(self, columns: Mapping[str, Any]) -> None:
        if isinstance(columns, Schema):
            columns = columns.specs
        if not isinstance(columns, Mapping):
            raise TypeError(f"o schema deve ser um dict {{nome: coluna}}, não {type(columns).__name__}")
        if not columns:
            raise ValueError("o schema não tem colunas")
        self._columns: dict[str, Spec] = {name: parse(name, spec) for name, spec in columns.items()}
        self._order = tuple(self._columns)
        self._levels = _levels(self._columns)

    # ------------------------------------------------------------------ consulta
    @property
    def names(self) -> tuple[str, ...]:
        """Nomes das colunas, na ordem do schema (a ordem da tabela gerada)."""
        return self._order

    @property
    def specs(self) -> dict[str, Spec]:
        return dict(self._columns)

    def __getitem__(self, name: str) -> Spec:
        return self._columns[name]

    def __len__(self) -> int:
        return len(self._order)

    def __iter__(self) -> Iterator[str]:
        return iter(self._order)

    def __contains__(self, name: object) -> bool:
        return name in self._columns

    def dependencies(self, name: str) -> frozenset[str]:
        """Colunas de que ``name`` depende diretamente."""
        return self._columns[name].dependencies

    def __repr__(self) -> str:
        parts = []
        for name, spec in self._columns.items():
            parts.append(f"{name}: {spec.kind}" if isinstance(spec, Column) else f"{name}: expr")
        return f"Schema({', '.join(parts)})"

    def select(self, names: Iterable[str]) -> Schema:
        """Schema só com ``names`` e as colunas de que elas dependem (direta ou indiretamente), na ordem original."""
        want = set()
        stack = list(names)
        while stack:
            c = stack.pop()
            if c not in self._columns:
                raise KeyError(f"a coluna {c!r} não está no schema")
            if c in want:
                continue
            want.add(c)
            stack.extend(self._columns[c].dependencies)
        sub = Schema.__new__(Schema)
        sub._columns = {k: v for k, v in self._columns.items() if k in want}
        sub._order = tuple(sub._columns)
        sub._levels = _levels(sub._columns)
        return sub

    # ------------------------------------------------------------------ execução
    def bind(self, locale: Locale) -> Schema:
        """Completa o que depende do locale (ex.: centro e escala de ``correlated``); devolve outro Schema se mudou."""
        changed: dict[str, Spec] = {}
        for name, spec in self._columns.items():
            if isinstance(spec, Column) and spec.kind in _MOMENT_KINDS:
                key, c_field, s_field = _MOMENT_KINDS[spec.kind]
                cfg = spec.config
                if getattr(cfg, c_field) is not None and getattr(cfg, s_field) is not None:
                    continue
                if key not in spec.refs:
                    continue  # sem a coluna: o próprio gerador explica o erro
                target = self._columns[spec.refs[key].column]
                moments = None
                if isinstance(target, Column):
                    moments = registry.get(target.kind).moments(target.config, locale)
                if moments is None:
                    what = f"o gerador {target.kind!r}" if isinstance(target, Column) else "uma expressão"
                    raise ValueError(
                        f"coluna {name!r}: a distribuição de {key!r} ({what}) não é conhecida; passe {c_field} e "
                        f"{s_field} (média e desvio padrão de {key!r})"
                    )
                update = {}
                if getattr(cfg, c_field) is None:
                    update[c_field] = moments[0]
                if getattr(cfg, s_field) is None:
                    update[s_field] = moments[1] if moments[1] > 0 else None
                changed[name] = Column(spec.kind, cfg.model_copy(update=update), spec.refs)
        if not changed:
            return self
        out = Schema.__new__(Schema)
        out._columns = {k: changed.get(k, v) for k, v in self._columns.items()}
        out._order = self._order
        out._levels = self._levels
        return out

    def run(self, ctx: Context, n: int, first_block: int = 0) -> pl.DataFrame:
        """Gera as linhas ``first_block * BLOCK_ROWS ..`` (``n`` linhas) da tabela. Use `bind` antes.

        Em cada nível: planeja as colunas (em paralelo: cada uma lê só as suas entradas), preenche os blocos (todas as
        colunas de um bloco de uma vez, blocos em paralelo) e monta as Series (em paralelo; inclui os dados sujos).
        """
        built: dict[str, pl.Series] = {}
        blocks = split(n, first_block)
        threads = ctx.threads
        for level in self._levels:
            cols = [self._columns[c] for c in level]
            gen = [c for c in cols if isinstance(c, Column)]
            for spec in gen:
                provider = registry.get(spec.kind)
                if provider.composite:  # monta a coluna sozinho (e paraleliza por dentro)
                    inputs = {k: built[r.column] for k, r in spec.refs.items()}
                    built[spec.name] = provider.generate(n, spec.config, ctx, inputs, first_block)
            fused = [c for c in gen if not registry.get(c.kind).composite]

            def prepare(spec: Column) -> Prepared:
                inputs = {k: built[r.column] for k, r in spec.refs.items()}
                return registry.get(spec.kind).prepare(n, spec.config, ctx, inputs, first_block)

            prepared = _map(prepare, fused, threads)
            if prepared:
                costs = [registry.get(c.kind).ns_per_row for c in fused]
                _fill(prepared, blocks, 1 if sum(costs) < PARALLEL_MIN_NS else threads, costs)
                for p, series in zip(prepared, _map(Prepared.finish, prepared, threads), strict=True):
                    built[p.run.name] = series
            for spec in cols:
                if isinstance(spec, ExprColumn):
                    built[spec.name] = _evaluate(spec, built, n)
        return pl.DataFrame([built[c] for c in self._order])


T = TypeVar("T")
R = TypeVar("R")


def _map(fn: Callable[[T], R], items: Sequence[T], threads: int | None) -> list[R]:
    """``[fn(x) for x in items]``, em paralelo quando há mais de um item e mais de uma thread (ordem preservada)."""
    return parallel_map(fn, items, threads)


def _fill(prepared: list[Prepared], blocks: list[Block], threads: int | None, costs: Sequence[float] = ()) -> None:
    """Preenche todos os blocos de todas as colunas. Com poucos blocos por thread (ex.: 1 milhão de linhas são 16
    blocos), cada bloco vira alguns grupos de colunas de custo parecido, para nenhuma thread ficar com a maior parte do
    trabalho no fim; cada tarefa escreve só nas fatias das suas colunas no seu bloco. ``costs``: ns/linha estimado de
    cada coluna (na ordem de ``prepared``); sem ele, todas contam igual."""
    workers = min(resolve_threads(threads), len(blocks) * len(prepared))
    k = -(-4 * workers // max(len(blocks), 1))
    groups = _cost_groups(prepared, list(costs) or [1.0] * len(prepared), k) if workers > 1 else [prepared]
    tasks = [(b, g) for b in blocks for g in groups]

    def one(task: tuple[Block, list[Prepared]]) -> None:
        b, group = task
        for p in group:
            p.fill(b)

    parallel_map(one, tasks, threads)


def _cost_groups(prepared: list[Prepared], costs: list[float], k: int) -> list[list[Prepared]]:
    """Divide as colunas em até ``k`` grupos de custo parecido (as mais caras primeiro, cada uma no grupo mais leve)."""
    k = max(1, min(k, len(prepared)))
    if k == 1:
        return [prepared]
    groups: list[list[Prepared]] = [[] for _ in range(k)]
    load = [0.0] * k
    for i in sorted(range(len(prepared)), key=lambda i: -costs[i]):
        j = load.index(min(load))
        groups[j].append(prepared[i])
        load[j] += costs[i]
    return [g for g in groups if g]


def _evaluate(spec: ExprColumn, built: Mapping[str, pl.Series], n: int) -> pl.Series:
    deps = sorted(spec.dependencies)
    frame = pl.DataFrame([built[c] for c in deps]) if deps else pl.DataFrame()
    try:
        expr = spec.expr.alias(spec.name)
        out = frame.select(expr).to_series() if deps else pl.select(expr).to_series()
    except Exception as exc:
        raise ValueError(f"coluna {spec.name!r}: a expressão falhou: {exc}") from exc
    if len(out) == 1 and n != 1:
        out = out.extend_constant(out[0], n - 1) if n > 1 else out.clear()
    if len(out) != n:
        raise ValueError(
            f"coluna {spec.name!r}: a expressão deu {len(out)} valores, esperava {n} (só vale expressão linha a linha)"
        )
    return out


def _levels(columns: Mapping[str, Spec]) -> tuple[tuple[str, ...], ...]:
    """Ordena as colunas em níveis de dependência (Kahn); erro claro para coluna inexistente e para ciclo."""
    for name, spec in columns.items():
        missing = sorted(spec.dependencies - columns.keys())
        if missing:
            raise ValueError(f"coluna {name!r} depende de colunas que não estão no schema: {', '.join(missing)}")
        if name in spec.dependencies:
            raise ValueError(f"coluna {name!r} depende dela mesma")
    done: set[str] = set()
    levels: list[tuple[str, ...]] = []
    remaining = list(columns)
    while remaining:
        ready = tuple(c for c in remaining if columns[c].dependencies <= done)
        if not ready:
            raise ValueError(f"dependência circular entre as colunas: {', '.join(remaining)}")
        levels.append(ready)
        done.update(ready)
        remaining = [c for c in remaining if c not in done]
    return tuple(levels)


@dataclass(frozen=True)
class _Batches:
    """Lotes de linhas alinhados aos blocos: ``(primeiro bloco, linhas)``."""

    total: int
    rows: int

    def __iter__(self) -> Iterator[tuple[int, int]]:
        start = 0
        while start < self.total:
            m = min(self.rows, self.total - start)
            yield start // BLOCK_ROWS, m
            start += m


def batch_rows(requested: int | None, default: int = 16 * BLOCK_ROWS) -> int:
    """Tamanho de lote arredondado para cima a um múltiplo de `BLOCK_ROWS` (os lotes começam em início de bloco)."""
    if requested is None or requested <= 0:
        return default
    return -(-requested // BLOCK_ROWS) * BLOCK_ROWS


def iter_batches(schema: Schema, ctx: Context, n: int, rows: int) -> Iterator[pl.DataFrame]:
    """A tabela de ``n`` linhas em lotes de ``rows`` linhas (múltiplo de `BLOCK_ROWS`); juntos dão `Schema.run`."""
    if rows % BLOCK_ROWS:
        raise ValueError(f"o lote deve ser múltiplo de {BLOCK_ROWS} linhas")
    for first_block, m in _Batches(n, rows):
        yield schema.run(ctx, m, first_block)


def as_schema(schema: Schema | Mapping[str, Any]) -> Schema:
    return schema if isinstance(schema, Schema) else Schema(schema)
