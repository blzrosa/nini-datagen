"""Configurações dos identificadores de rede: UUID, IPv4, IPv6, MAC e URL."""

from __future__ import annotations

from .base import BaseConfig

__all__ = ["IPv4Config", "IPv6Config", "MACConfig", "URLConfig", "UUIDConfig"]


class UUIDConfig(BaseConfig):
    """UUID versão 4 (aleatório), minúsculo com hifens: ``"3f2b8c1e-9a4d-4f6b-8e21-0c7d5a9b1f34"``."""


class IPv4Config(BaseConfig):
    """Endereço IPv4.

    ``private=False``: público (1-223, sem 10/8, 127/8, 172.16/12, 192.168/16, 169.254/16, 100.64/10, 198.18/15 e as
    redes de documentação). ``private=True``: 10/8, 172.16/12 ou 192.168/16, um terço cada.
    """

    private: bool = False


class IPv6Config(BaseConfig):
    """Endereço IPv6 completo (8 grupos de 4 dígitos hexadecimais minúsculos, sem abreviação)."""


class MACConfig(BaseConfig):
    """Endereço MAC unicast: ``"3a:1f:9c:00:7e:b2"``."""


class URLConfig(BaseConfig):
    """URL plausível: ``https://[www.]palavra[-palavra].tld[/trecho...][?pagina=N]`` (palavras e TLDs do locale)."""
