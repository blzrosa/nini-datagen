"""Base das configurações: modelos Pydantic imutáveis que recusam campos desconhecidos."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .dirty import DirtyConfig

__all__ = ["BaseConfig", "Probability"]


class BaseConfig(BaseModel):
    """Campos comuns a todo gerador.

    * ``name``: nome da coluna gerada (padrão: o tipo do gerador, ex. ``"cpf"``). Também identifica o fluxo de números
      aleatórios: com a mesma ``seed``, duas colunas com nomes diferentes saem independentes, e a mesma coluna sai
      sempre igual.
    * ``null_fraction``: fração esperada de nulos, sorteados linha a linha num fluxo próprio (mudar só a fração não
      muda os valores das linhas que continuam preenchidas).
    * ``dirty``: dados sujos (`DirtyConfig` ou dict: ``{"typo": 0.02, "unmask": 0.3}``), também em fluxos próprios.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True, str_strip_whitespace=False)

    name: str | None = Field(default=None, min_length=1)
    null_fraction: float = Field(default=0.0, ge=0.0, le=1.0)
    dirty: DirtyConfig | None = None

    @field_validator("null_fraction")
    @classmethod
    def _finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("deve ser finito")
        return v


def Probability(default: float | None, description: str = "") -> Any:  # noqa: N802 (fábrica de campo, como Field)
    """Campo de probabilidade em [0, 1]."""
    return Field(default=default, ge=0.0, le=1.0, allow_inf_nan=False, description=description)
