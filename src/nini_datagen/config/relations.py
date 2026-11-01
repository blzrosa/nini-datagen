"""Configurações dos geradores que dependem de outra coluna: nascimento pela idade, correlação e escolha condicional."""

from __future__ import annotations

import datetime as dt
import math
import warnings
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import Field, field_validator

from .base import BaseConfig

__all__ = ["BirthdateConfig", "ChoiceByConfig", "CorrelatedConfig"]


def _today_with_warning() -> dt.date:
    warnings.warn(
        "birthdate sem `on`: usando a data de hoje, e os dados mudam de um dia para o outro. "
        "Passe `on` (ex.: on='2026-01-01'); será obrigatório na 0.3.0.",
        FutureWarning,
        stacklevel=2,
    )
    return dt.date.today()


class BirthdateConfig(BaseConfig):
    """Data de nascimento (Date) coerente com uma coluna de idades: quem tem ``a`` anos em ``on`` nasceu no intervalo
    ``(on - a - 1 anos, on - a anos]``, sorteado uniformemente. A coluna de idade vai como dado:
    ``birthdate(n, age=idades)`` ou ``("birthdate", {"age": dg.ref("idade")})`` numa tabela.

    ``on``: a data de referência. Passe sempre: sem ela, usa o dia em que a configuração é criada (e os dados mudam
    de um dia para o outro), com um ``FutureWarning``; na 0.3.0 passa a ser obrigatória. Idade nula dá data nula;
    29/02 vira 28/02 em ano não bissexto.
    """

    on: dt.date = Field(default_factory=_today_with_warning)


class CorrelatedConfig(BaseConfig):
    """Real (Float64) com correlação ``rho`` com uma coluna numérica (``other``, que vai como dado):

    ``y = mean + std * (rho * z + sqrt(1 - rho²) * e)``, com ``z = (other - center) / scale`` e ``e ~ Normal(0, 1)``.
    Com ``lognormal=True`` sai ``exp(y)`` (a correlação vale na escala do log: renda x idade, preço x área).

    ``center`` e ``scale``: média e desvio padrão de ``other``. Numa tabela, com ``ref`` para um gerador de
    distribuição conhecida (integer, uniform, normal, lognormal, age), vêm da distribuição dele; para uma coluna
    passada como dado, da própria coluna. Nulos em ``other`` contam como ``center``.
    """

    rho: float = Field(ge=-1.0, le=1.0, allow_inf_nan=False)
    mean: float = Field(default=0.0, allow_inf_nan=False)
    std: float = Field(default=1.0, ge=0.0, allow_inf_nan=False)
    lognormal: bool = False
    center: float | None = Field(default=None, allow_inf_nan=False)
    scale: float | None = Field(default=None, gt=0.0, allow_inf_nan=False)


Options = tuple[tuple[str, ...], tuple[float, ...] | None]


def _options(value: Any, where: str) -> Options:
    """``["a", "b"]`` ou ``(["a", "b"], [3, 1])`` -> (valores, pesos ou None), com os valores como texto."""
    if isinstance(value, tuple) and len(value) == 2 and not isinstance(value[1], str) and value[1] is not None:
        vals, weights = value
    else:
        vals, weights = value, None
    if isinstance(vals, str) or not isinstance(vals, Sequence) or not vals:
        raise ValueError(f"{where}: precisa de uma lista não vazia de opções")
    out = tuple(str(v) for v in vals)
    if weights is None:
        return out, None
    w = tuple(float(x) for x in weights)
    if len(w) != len(out):
        raise ValueError(f"{where}: {len(out)} opções e {len(w)} pesos")
    if any(not math.isfinite(x) or x < 0 for x in w) or sum(w) <= 0:
        raise ValueError(f"{where}: pesos devem ser finitos, >= 0 e com soma > 0")
    return out, w


class ChoiceByConfig(BaseConfig):
    """Escolha condicionada a outra coluna (``by``, que vai como dado): para cada valor de ``by``, sorteia entre as
    opções de ``options`` (``{valor: lista}`` ou ``{valor: (lista, pesos)}``). Ex.: modelo por marca, cargo por área.

    ``default``: opções para valores de ``by`` que não estão em ``options`` (e para nulos); sem ``default``, essas
    linhas saem nulas. Os valores de ``by`` são comparados como texto; a saída é texto.
    """

    options: dict[str, Options]
    default: Options | None = None

    @field_validator("options", mode="before")
    @classmethod
    def _parse_options(cls, v: Any) -> dict[str, Options]:
        if not isinstance(v, Mapping) or not v:
            raise ValueError("options deve ser um dict não vazio {valor: opções}")
        return {str(k): _options(o, f"options[{k!r}]") for k, o in v.items()}

    @field_validator("default", mode="before")
    @classmethod
    def _parse_default(cls, v: Any) -> Options | None:
        return None if v is None else _options(v, "default")
