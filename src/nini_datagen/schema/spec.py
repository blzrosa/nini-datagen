"""Como cada coluna de um schema é descrita: referência a outra coluna (`ref`), coluna de gerador (`Column`) e a
leitura das formas curtas aceitas num dict (``"cpf"``, ``("cpf", {...})``, ``CPFConfig(...)``, ``pl.col(...) * 2``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import polars as pl

from ..config.base import BaseConfig
from ..registry import registry

__all__ = ["Column", "ExprColumn", "Ref", "Spec", "column", "parse", "ref"]


@dataclass(frozen=True, slots=True)
class Ref:
    """Referência a outra coluna do mesmo schema: ``("first_name", {"sex": dg.ref("sexo")})``.

    A coluna referida é gerada antes e entra como dado no gerador (só nos argumentos de dados: ``sex`` de
    ``first_name``/``full_name``, ``age`` de ``birthdate``, ``other`` de ``correlated``, ``by`` de ``choice_by``).
    """

    column: str

    def __post_init__(self) -> None:
        if not isinstance(self.column, str) or not self.column:
            raise ValueError("ref precisa do nome de uma coluna")

    def __repr__(self) -> str:
        return f"ref({self.column!r})"


def ref(column: str) -> Ref:
    """Referência a outra coluna do schema (veja `Ref`)."""
    return Ref(column)


@dataclass(frozen=True)
class Column:
    """Uma coluna de gerador já validada: tipo, configuração (com ``name`` = nome da coluna) e referências."""

    kind: str
    config: BaseConfig
    refs: Mapping[str, Ref] = field(default_factory=dict)

    @property
    def name(self) -> str:
        assert self.config.name is not None
        return self.config.name

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset(r.column for r in self.refs.values())


@dataclass(frozen=True)
class ExprColumn:
    """Coluna calculada por uma expressão do Polars sobre outras colunas (``pl.col("idade") * 12``)."""

    name: str
    expr: pl.Expr

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset(self.expr.meta.root_names())


Spec = Column | ExprColumn


@dataclass(frozen=True)
class _Pending:
    """`column(...)` sem nome: o nome vem da chave do schema."""

    kind: str
    config: Any
    kwargs: Mapping[str, Any]


def column(kind: str, config: Any = None, /, **kwargs: Any) -> Any:
    """Coluna de gerador para um schema, com a mesma assinatura de `DataGen.generate` (sem ``n``):

    >>> dg.column("first_name", sex=dg.ref("sexo"))      # doctest: +SKIP
    >>> dg.column("choice", ["a", "b"], weights=[3, 1])  # doctest: +SKIP

    O nome é a chave do schema. Equivale a ``(kind, {...})`` no dict, mas aceita o segundo argumento posicional.
    """
    registry.get(kind)  # erro cedo para tipo inexistente
    return _Pending(kind, config, dict(kwargs))


def _take_refs(name: str, kind: str, args: dict[str, Any], inputs: tuple[str, ...], refs: dict[str, Ref]) -> None:
    """Tira de ``args`` os `Ref` (para ``refs``); recusa ref fora dos argumentos de dados e dados soltos."""
    for key, value in list(args.items()):
        if isinstance(value, Ref):
            if key not in inputs:
                ok = ", ".join(inputs) or "nenhum"
                raise ValueError(f"coluna {name!r}: ref só vale nos argumentos de dados de {kind} ({ok}), não {key!r}")
            refs[key] = args.pop(key)


def _build(name: str, kind: str, config: Any, kwargs: Mapping[str, Any]) -> Column:
    provider = registry.get(kind)
    refs: dict[str, Ref] = {}
    kw = dict(kwargs)
    _take_refs(name, kind, kw, provider.inputs, refs)
    if isinstance(config, Mapping):
        config = dict(config)
        _take_refs(name, kind, config, provider.inputs, refs)
    loose = list(provider.take_inputs(kw)) + (list(provider.take_inputs(config)) if isinstance(config, dict) else [])
    if loose:
        raise ValueError(f"coluna {name!r}: num schema, {', '.join(loose)} deve ser dg.ref('outra_coluna'), não dados")
    given = kw.get("name")
    if given is None and isinstance(config, Mapping):
        given = config.get("name")
    if given is None and isinstance(config, BaseConfig):
        given = config.name
    if given is not None and given != name:
        raise ValueError(f"coluna {name!r}: o nome vem da chave do schema (veio name={given!r})")
    cfg = registry.config(kind, config, **{**kw, "name": name})
    return Column(kind, cfg, refs)


def _shorthand(spec: Any) -> tuple[str, Any] | None:
    """Formas curtas -> (tipo, configuração); None se não é uma delas."""
    if isinstance(spec, str):
        return spec, None
    if isinstance(spec, BaseConfig):
        return registry.kind_of(spec), spec
    ok = isinstance(spec, tuple) and len(spec) == 2 and isinstance(spec[0], str)
    if ok and (spec[1] is None or isinstance(spec[1], Mapping | BaseConfig)):
        return spec
    return None


def parse(name: Any, spec: Any) -> Spec:
    """Uma entrada do dict do schema -> `Column` ou `ExprColumn`."""
    if not isinstance(name, str) or not name:
        raise ValueError(f"nome de coluna inválido: {name!r}")
    if isinstance(spec, pl.Expr):
        return ExprColumn(name, spec)
    if isinstance(spec, Column):
        if spec.name == name:
            return spec
        return _build(name, spec.kind, spec.config.model_copy(update={"name": None}), dict(spec.refs))
    if isinstance(spec, _Pending):
        return _build(name, spec.kind, spec.config, spec.kwargs)
    short = _shorthand(spec)
    if short is None:
        raise TypeError(
            f"coluna {name!r}: use 'tipo', ('tipo', {{...}}), uma configuração (dg.CPFConfig(...)), dg.column(...) "
            f"ou uma expressão do Polars; veio {spec!r}"
        )
    return _build(name, short[0], short[1], {})
