"""Configurações de contato: telefone, e-mail e nome de usuário."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .base import BaseConfig

__all__ = ["EmailConfig", "PhoneConfig", "UsernameConfig"]


class PhoneConfig(BaseConfig):
    """Telefone brasileiro: celular ``(DD) 9XXXX-XXXX`` ou fixo ``(DD) NXXX-XXXX`` (N de 2 a 5).

    * ``style``: ``"digits"`` (``"11987654321"``), ``"masked"`` (``"(11) 98765-4321"``) ou ``"intl"``
      (``"+5511987654321"``).
    * ``mobile``: fração de celulares.
    * ``uf``: só DDDs dessa UF (``"SP"``); sem ``uf``, o DDD sai com peso pela população da UF (dividida entre os DDDs
      dela).
    """

    style: Literal["digits", "masked", "intl"] = "digits"
    mobile: float = Field(default=0.8, ge=0.0, le=1.0)
    uf: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("uf")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return None if v is None else v.upper()


class UsernameConfig(BaseConfig):
    """Nome de usuário a partir de nome e sobrenome sem acento, em 8 estilos: ``maria.silva``, ``maria_silva``,
    ``mariasilva``, ``maria.silva23``, ``mariasilva23``, ``msilva``, ``mariasilva1987`` e ``silva.maria``.

    ``style_weights``: um peso por estilo, nessa ordem (padrão: 28, 7, 12, 12, 10, 10, 9, 12).
    """

    style_weights: tuple[float, ...] | None = Field(default=None, min_length=8, max_length=8)

    @field_validator("style_weights")
    @classmethod
    def _weights(cls, v: tuple[float, ...] | None) -> tuple[float, ...] | None:
        if v is not None and (any(not w >= 0 for w in v) or sum(v) <= 0):
            raise ValueError("style_weights: pesos >= 0 com soma positiva")
        return v


class EmailConfig(UsernameConfig):
    """E-mail: nome de usuário (como em `UsernameConfig`) + ``@`` + domínio.

    ``domains``: domínios próprios (padrão: os do locale, com peso); ``domain_weights``: um peso por domínio.
    """

    domains: tuple[str, ...] | None = Field(default=None, min_length=1)
    domain_weights: tuple[float, ...] | None = None

    @field_validator("domains")
    @classmethod
    def _domains(cls, v: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if v is not None:
            for d in v:
                if not d or len(d) > 24 or not d.isascii() or "@" in d or " " in d:
                    raise ValueError(f"domínio inválido: {d!r} (ASCII, sem espaço nem @, até 24 caracteres)")
            v = tuple(d.lower() for d in v)
        return v

    @model_validator(mode="after")
    def _weights_match(self) -> EmailConfig:
        if self.domain_weights is not None:
            if self.domains is None:
                raise ValueError("domain_weights precisa de domains")
            if len(self.domain_weights) != len(self.domains):
                raise ValueError(f"domain_weights deve ter {len(self.domains)} pesos (um por domínio)")
            if any(not w >= 0 for w in self.domain_weights) or sum(self.domain_weights) <= 0:
                raise ValueError("domain_weights: pesos >= 0 com soma positiva")
        return self
