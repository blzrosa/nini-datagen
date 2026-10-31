"""Registro dos geradores por nome (Registry) e montagem das configurações (Factory).

Um tipo novo entra só com ``@registry.register`` na classe do provider: o motor, o `DataGen` e as tabelas o encontram
pelo nome, sem editar mais nada.
"""

from __future__ import annotations

import difflib
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, TypeVar

from .config.base import BaseConfig

if TYPE_CHECKING:
    from .providers.base import Provider

__all__ = ["Registry", "registry"]

P = TypeVar("P", bound="Provider[Any]")


class Registry:
    def __init__(self) -> None:
        self._providers: dict[str, Provider[Any]] = {}

    def register(self, cls: type[P]) -> type[P]:
        """Decorador de classe: registra uma instância do provider com o nome ``cls.kind``."""
        kind = cls.kind
        if kind in self._providers:
            raise ValueError(f"o tipo {kind!r} já está registrado")
        self._providers[kind] = cls()
        return cls

    def get(self, kind: str) -> Provider[Any]:
        try:
            return self._providers[kind]
        except KeyError:
            near = difflib.get_close_matches(kind, self._providers, n=3)
            hint = f" Você quis dizer: {', '.join(near)}?" if near else ""
            raise KeyError(f"gerador {kind!r} não existe.{hint} Disponíveis: {', '.join(self.kinds())}") from None

    def __contains__(self, kind: object) -> bool:
        return kind in self._providers

    def kinds(self) -> list[str]:
        return sorted(self._providers)

    def kind_of(self, config: BaseConfig) -> str:
        """Tipo do gerador de uma configuração (``CPFConfig(...)`` -> ``"cpf"``)."""
        found = [k for k, p in self._providers.items() if type(config) is p.config_cls]
        if len(found) != 1:
            what = "nenhum gerador" if not found else f"vários geradores ({', '.join(found)})"
            raise TypeError(f'{type(config).__name__} é usado por {what}; diga o tipo: ("tipo", config)')
        return found[0]

    def config(self, kind: str, config: Any = None, **kwargs: Any) -> BaseConfig:
        """Monta (e valida) a configuração de ``kind`` a partir de um objeto de config, um dict e/ou kwargs.

        ``kwargs`` têm prioridade sobre ``config``. O provider pode aceitar um valor posicional (ex.: a lista de
        ``choice``) no lugar de ``config``.
        """
        provider = self.get(kind)
        cls = provider.config_cls
        if config is None:
            base: dict[str, Any] = {}
        elif isinstance(config, cls):
            if not kwargs:
                return config
            base = config.model_dump(exclude_unset=True)
        elif isinstance(config, BaseConfig):
            raise TypeError(f"{kind} espera {cls.__name__}, não {type(config).__name__}")
        elif isinstance(config, Mapping):
            base = dict(config)
        elif provider.positional is not None and (values := _as_list(config)) is not None:
            base = {provider.positional: values}
        else:
            raise TypeError(f"config de {kind} deve ser {cls.__name__}, dict ou None, não {type(config).__name__}")
        return cls.model_validate({**base, **kwargs})


def _as_list(x: Any) -> list[Any] | None:
    """Lista, tupla, array numpy ou Series do Polars -> lista Python (com escalares nativos); outra coisa -> None."""
    if isinstance(x, str | bytes):
        return None
    if hasattr(x, "to_list"):  # pl.Series
        return list(x.to_list())
    if hasattr(x, "tolist"):  # np.ndarray
        out = x.tolist()
        return out if isinstance(out, list) else None
    if isinstance(x, Sequence):
        return [v.item() if hasattr(v, "item") else v for v in x]
    return None


registry = Registry()
