"""Configuração dos dados sujos (`DirtyConfig`): que fração das linhas recebe cada defeito."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = ["NULL_TOKENS", "TEXT_DEFECTS", "DirtyConfig"]

NULL_TOKENS: tuple[str, ...] = ("", "N/A", "n/a", "NULL", "null", "-", "?", "nulo", "NaN", "None", "não informado")
TEXT_DEFECTS = ("accents", "mojibake", "unmask", "typo", "truncate", "case", "whitespace", "null_like")


def _fraction(description: str) -> Any:
    return Field(default=0.0, ge=0.0, le=1.0, allow_inf_nan=False, description=description)


class DirtyConfig(BaseModel):
    """Defeitos de dados reais, cada um numa fração das linhas (sorteada linha a linha, num fluxo próprio).

    Texto:

    * ``accents``: tira os acentos (``"São Paulo"`` -> ``"Sao Paulo"``);
    * ``mojibake``: UTF-8 lido como Latin-1 (``"São"`` -> ``"SÃ£o"``);
    * ``unmask``: tira pontos, traços, barras, parênteses e espaços (CPF, CNPJ, CEP, telefone);
    * ``typo``: um erro de digitação (apaga, troca com a vizinha, repete ou substitui uma letra);
    * ``truncate``: corta o fim (sobra pelo menos um caractere);
    * ``case``: tudo maiúsculo ou tudo minúsculo;
    * ``whitespace``: espaço sobrando no começo, no fim ou nos dois;
    * ``null_like``: vira um texto que quer dizer "vazio" (``null_tokens``: ``""``, ``"N/A"``, ``"NULL"``, ``"-"``...).

    Números: ``outliers`` multiplica por um fator de ``outlier_factors`` (padrão ``-1, 10, 100, 1000``).
    Qualquer tipo: ``sentinel=[(valor, fração), ...]`` troca pelo valor (ex.: ``[(-1, 0.01), (0, 0.02)]``, ``9999``).

    Os defeitos são aplicados nesta ordem e um valor pode receber mais de um. Nulos continuam nulos (menos em
    ``null_like`` e ``sentinel``, que substituem o valor).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    accents: float = _fraction("tirar acentos")
    mojibake: float = _fraction("UTF-8 lido como Latin-1")
    unmask: float = _fraction("tirar pontuação de máscara")
    typo: float = _fraction("um erro de digitação")
    truncate: float = _fraction("cortar o fim")
    case: float = _fraction("maiúsculas ou minúsculas")
    whitespace: float = _fraction("espaços sobrando")
    null_like: float = _fraction("texto de vazio")
    null_tokens: tuple[str, ...] = NULL_TOKENS
    outliers: float = _fraction("multiplicar por um fator")
    outlier_factors: tuple[float, ...] = (-1.0, 10.0, 100.0, 1000.0)
    sentinel: tuple[tuple[Any, float], ...] = ()

    @field_validator("null_tokens", "outlier_factors")
    @classmethod
    def _not_empty(cls, v: tuple[Any, ...]) -> tuple[Any, ...]:
        if not v:
            raise ValueError("precisa de pelo menos um valor")
        return v

    @field_validator("outlier_factors")
    @classmethod
    def _finite(cls, v: tuple[float, ...]) -> tuple[float, ...]:
        if any(not math.isfinite(x) for x in v):
            raise ValueError("os fatores devem ser finitos")
        return v

    @field_validator("sentinel", mode="before")
    @classmethod
    def _pairs(cls, v: Any) -> Any:
        out = []
        for item in v or ():
            if not isinstance(item, tuple | list) or len(item) != 2:
                raise ValueError("sentinel é uma lista de pares (valor, fração)")
            value, frac = item
            if isinstance(frac, bool) or not isinstance(frac, int | float) or not 0.0 <= frac <= 1.0:
                raise ValueError(f"fração do sentinela {value!r} deve estar entre 0 e 1")
            out.append((value, float(frac)))
        return tuple(out)

    @property
    def text_ops(self) -> list[tuple[str, float]]:
        return [(op, getattr(self, op)) for op in TEXT_DEFECTS if getattr(self, op) > 0]

    @property
    def is_empty(self) -> bool:
        return not self.text_ops and self.outliers <= 0 and not any(f > 0 for _, f in self.sentinel)
