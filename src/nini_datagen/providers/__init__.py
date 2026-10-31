"""Geradores (um provider por tipo). Importar este pacote registra todos no `registry`."""

from __future__ import annotations

from . import address, business, choice, contact, documents, network, numbers, person, text
from .base import Context, Job, Provider, Run

__all__ = [
    "Context",
    "Job",
    "Provider",
    "Run",
    "address",
    "business",
    "choice",
    "contact",
    "documents",
    "network",
    "numbers",
    "person",
    "text",
]
