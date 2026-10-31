"""Configurações dos geradores de pessoa: sexo, idade e nomes."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .base import BaseConfig, Probability

__all__ = ["AgeConfig", "FirstNameConfig", "FullNameConfig", "LastNameConfig", "SexConfig"]

Sex = Literal["F", "M"]


class SexConfig(BaseConfig):
    """Sexo, com ``p_female`` de mulheres (padrão: a proporção do locale; no pt_BR, 51,5% pelo Censo 2022).

    ``labels``: os dois textos de saída, feminino primeiro (padrão ``("F", "M")``).
    """

    p_female: float | None = Probability(None, "fração de mulheres; None = a do locale")
    labels: tuple[str, str] = ("F", "M")

    @model_validator(mode="after")
    def _check(self) -> SexConfig:
        if self.labels[0] == self.labels[1]:
            raise ValueError("labels precisa de dois textos diferentes")
        return self


class AgeConfig(BaseConfig):
    """Idades inteiras (Int32) em ``[low, high]``.

    ``weights``: um peso por idade, de ``low`` a ``high``; o padrão é a pirâmide etária do locale.
    """

    low: int = Field(default=0, ge=0, le=150)
    high: int = Field(default=100, ge=0, le=150)
    weights: tuple[float, ...] | None = None

    @model_validator(mode="after")
    def _check(self) -> AgeConfig:
        if self.high < self.low:
            raise ValueError(f"high ({self.high}) deve ser >= low ({self.low})")
        if self.weights is not None:
            from ..core.tables import check_weights  # noqa: PLC0415

            check_weights(self.weights, self.high - self.low + 1)
        return self


class FirstNameConfig(BaseConfig):
    """Primeiros nomes com a frequência real (no pt_BR, Censo do IBGE).

    ``sex``: ``"F"`` ou ``"M"`` sorteia só nomes daquele sexo, com a frequência por sexo; ``None`` usa todos. Para
    nomes coerentes com uma coluna de sexo, passe a coluna em ``first_name(n, sex=serie)``.
    """

    sex: Sex | None = None


class LastNameConfig(BaseConfig):
    """Sobrenomes com a frequência real (no pt_BR, candidatos do TSE em 2024)."""


class FullNameConfig(BaseConfig):
    """Nome completo: um ou dois prenomes + um ou dois sobrenomes (``"Maria Eduarda Souza Lima"``).

    * ``compound``: probabilidade de prenome composto (o segundo prenome é do mesmo sexo e diferente do primeiro).
    * ``two_surnames``: probabilidade de dois sobrenomes (nunca o mesmo duas vezes).
    * ``sex``: como em `FirstNameConfig`; sem sexo, cada linha sorteia o seu (com a proporção do locale), para que os
      dois prenomes combinem.

    Os padrões são estimativas do formato mais comum no Brasil (a maioria das pessoas tem dois sobrenomes), não uma
    estatística oficial: ajuste à vontade.
    """

    sex: Sex | None = None
    compound: float = Probability(0.25, "probabilidade de prenome composto")
    two_surnames: float = Probability(0.9, "probabilidade de ter dois sobrenomes")
