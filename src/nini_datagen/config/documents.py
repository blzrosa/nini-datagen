"""Configurações dos documentos brasileiros e códigos (todos com dígito verificador válido)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .base import BaseConfig

__all__ = [
    "CNHConfig",
    "CNPJConfig",
    "CPFConfig",
    "CreditCardConfig",
    "EAN13Config",
    "IBANConfig",
    "LicensePlateConfig",
    "PISConfig",
    "RGConfig",
    "VoterIDConfig",
]


class CPFConfig(BaseConfig):
    """CPF com dígitos verificadores corretos.

    * ``formatted``: ``"123.456.789-09"`` em vez de ``"12345678909"``.
    * ``unique``: sem repetição (até 10^9 linhas). A linha ``i`` recebe a base ``perm(i)``, uma permutação de
      ``[0, 10^9)`` com chave tirada da semente (cifra de Feistel): parece aleatória, mas nunca repete.
    """

    formatted: bool = False
    unique: bool = False


class CNPJConfig(BaseConfig):
    """CNPJ: 8 caracteres de raiz + 4 de ordem + 2 dígitos verificadores.

    * ``alphanumeric``: raiz e ordem com 0-9 e A-Z (formato que a Receita começa a emitir em julho de 2026); os DV
      continuam numéricos. Padrão: só dígitos.
    * ``branch``: a ordem (4 caracteres), por padrão ``"0001"`` (matriz); ``None`` sorteia os 4.
    * ``formatted``: ``"12.345.678/0001-95"``.
    * ``unique``: sem repetição, pela mesma permutação com chave do CPF (até 10^8 linhas com ordem fixa, 10^12
      sorteando a ordem; 36^8 e 36^12 no alfanumérico).
    """

    alphanumeric: bool = False
    branch: str | None = Field(default="0001", min_length=4, max_length=4)
    formatted: bool = False
    unique: bool = False

    @field_validator("branch")
    @classmethod
    def _branch(cls, v: str | None) -> str | None:
        if v is not None and not all(c.isdigit() or "A" <= c <= "Z" for c in v):
            raise ValueError("a ordem só pode ter 0-9 e A-Z")
        return v

    @model_validator(mode="after")
    def _letters_need_alphanumeric(self) -> CNPJConfig:
        if self.branch is not None and not self.alphanumeric and not self.branch.isdigit():
            raise ValueError(f"a ordem {self.branch!r} tem letra: use alphanumeric=True")
        return self


class PISConfig(BaseConfig):
    """PIS/PASEP/NIS: ``"12345678919"`` ou, com ``formatted``, ``"123.45678.91-9"``."""

    formatted: bool = False


class VoterIDConfig(BaseConfig):
    """Título de eleitor (12 dígitos: sequência, UF e 2 DV): ``"123456780191"`` ou ``"1234 5678 0191"``.

    Válido nas duas leituras da regra de SP/MG (Resolução TSE e a usual): as linhas ambíguas são evitadas.
    """

    formatted: bool = False


class CNHConfig(BaseConfig):
    """Número de registro da CNH (11 dígitos, 2 DV)."""


class RGConfig(BaseConfig):
    """RG no padrão de SP (8 dígitos + DV 0-9 ou X): ``"123456789"`` ou ``"12.345.678-9"``."""

    formatted: bool = False


class LicensePlateConfig(BaseConfig):
    """Placa de veículo: ``"mercosul"`` (``"ABC1D23"``) ou ``"old"`` (``"ABC-1234"``)."""

    style: Literal["mercosul", "old"] = "mercosul"


class CreditCardConfig(BaseConfig):
    """Número de cartão com dígito de Luhn correto (não é um cartão real).

    ``brand``: ``"visa"`` (16 dígitos, começa com 4), ``"mastercard"`` (51-55), ``"amex"`` (15 dígitos, 34/37) ou
    ``"mixed"`` (55% Visa, 38% Mastercard, 7% Amex). ``formatted``: grupos separados por espaço.
    """

    brand: Literal["visa", "mastercard", "amex", "mixed"] = "mixed"
    formatted: bool = False


class IBANConfig(BaseConfig):
    """IBAN do Brasil (29 caracteres, DV módulo 97 correto); banco, agência e conta são aleatórios."""


class EAN13Config(BaseConfig):
    """Código de barras EAN-13 com prefixo 789 (Brasil) e DV correto."""
