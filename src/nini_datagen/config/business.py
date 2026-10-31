"""Configurações de empresa, veículo e profissão."""

from __future__ import annotations

from pydantic import Field, model_validator

from .base import BaseConfig

__all__ = ["CompanyConfig", "OccupationConfig", "VehicleConfig"]


class CompanyConfig(BaseConfig):
    """Razão social plausível: ``"Silva Comércio de Alimentos LTDA"`` (60%), ``"Santos & Lima Engenharia ME"`` (20%)
    ou ``"Nova Estrela Informática EPP"`` (20%). Sobrenomes com o peso da base do locale."""


class VehicleConfig(BaseConfig):
    """Veículo como struct ``{brand, model, year}``: modelo coerente com a marca, anos recentes mais comuns (peso
    crescendo linearmente de 1 a 4 entre ``year_low`` e ``year_high``). Amostra plausível do mercado, não é a FIPE.

    Para colunas separadas: ``g.vehicle(n).struct.unnest()``.
    """

    year_low: int = Field(default=2005, ge=1900, le=2100)
    year_high: int = Field(default=2025, ge=1900, le=2100)

    @model_validator(mode="after")
    def _years(self) -> VehicleConfig:
        if self.year_high < self.year_low:
            raise ValueError("year_high deve ser >= year_low")
        return self


class OccupationConfig(BaseConfig):
    """Profissão, das mais comuns às mais raras do locale (pesos de Zipf com expoente ``zipf``; 0 = uniforme)."""

    zipf: float = Field(default=0.7, ge=0.0, le=3.0)
