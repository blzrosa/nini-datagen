"""Configuração da escolha em lista."""

from __future__ import annotations

from pydantic import Field, model_validator

from .base import BaseConfig

__all__ = ["ChoiceConfig"]


class ChoiceConfig(BaseConfig):
    """Valores sorteados (com reposição) de ``values``: uniformes, ou proporcionais a ``weights`` (um por valor).

    ``values`` pode ser de textos (coluna String), inteiros (Int64), reais (Float64) ou booleanos (Boolean), sem
    misturar tipos.
    """

    values: tuple[bool, ...] | tuple[int, ...] | tuple[float, ...] | tuple[str, ...] = Field(min_length=1)
    weights: tuple[float, ...] | None = None

    @model_validator(mode="after")
    def _check(self) -> ChoiceConfig:
        if len(self.values) >= 2**31:
            raise ValueError("valores demais (máximo 2^31 - 1)")
        if self.weights is not None:
            from ..core.tables import check_weights  # noqa: PLC0415 (evita carregar a biblioteca C++ ao importar)

            check_weights(self.weights, len(self.values))
        return self
