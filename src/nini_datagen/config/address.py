"""Configurações de endereço: CEP, endereço completo (struct), cidade e UF."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from .base import BaseConfig

__all__ = ["AddressConfig", "CepConfig", "CityConfig", "StateConfig"]

Source = Literal["auto", "full", "lite"]


def _ufs(v: Any) -> tuple[str, ...] | None:
    if v is None:
        return None
    items = [v] if isinstance(v, str) else list(v)
    if not items or not all(isinstance(u, str) and len(u) == 2 for u in items):
        raise ValueError("uf deve ser uma sigla ('SP') ou uma lista de siglas")
    return tuple(sorted({u.upper() for u in items}))


class _ByUF(BaseConfig):
    uf: tuple[str, ...] | None = None

    @field_validator("uf", mode="before")
    @classmethod
    def _uf(cls, v: Any) -> tuple[str, ...] | None:
        return _ufs(v)


class CepConfig(_ByUF):
    """CEP real do CNEFE (IBGE, Censo 2022), com o peso do número de endereços.

    * ``formatted``: ``"01310-100"`` (padrão) ou ``"01310100"``.
    * ``uf``: só dessas UFs (``"SP"`` ou ``["SP", "RJ"]``).
    * ``source``: ``"auto"`` (a base completa, se baixada com ``datasets.download("cnefe")``; senão a leve, que vem no
      pacote), ``"full"`` ou ``"lite"``.
    """

    formatted: bool = True
    source: Source = "auto"


class AddressConfig(_ByUF):
    """Endereço real do CNEFE como struct ``{street, number, complement, neighborhood, city, state, cep}``: rua, bairro,
    cidade, UF e CEP existem juntos, sorteados pelo número de endereços do trecho.

    * ``number``: da faixa real do trecho (base completa) ou de uma lognormal entre 1 e 9999 (base leve).
    * ``complement``: fração das linhas com complemento (as outras ficam nulas).
    * ``phone``: acrescenta ``phone`` com o DDD da UF da linha (``"(11) 98765-4321"``).
    * ``coords``: acrescenta ``latitude`` e ``longitude`` (média dos endereços do trecho; 3 casas na base leve).
    * ``full``: acrescenta ``full``: ``"Rua X, 123 - Bairro, Cidade - UF, 01310-100"``.
    * ``uf`` e ``source``: como em `CepConfig`.

    Para colunas separadas: ``g.address(n).struct.unnest()``.
    """

    complement: float = Field(default=0.25, ge=0.0, le=1.0)
    phone: bool = False
    coords: bool = False
    full: bool = False
    source: Source = "auto"


class CityConfig(_ByUF):
    """Município com o peso da população (IBGE). ``with_state=True``: ``"Campinas/SP"`` (os nomes se repetem entre
    UFs)."""

    with_state: bool = False


class StateConfig(BaseConfig):
    """UF (sigla), com o peso da população (``weighted=False``: uniforme)."""

    weighted: bool = True
