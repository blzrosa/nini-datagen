"""Geradores (um provider por tipo). Importar este pacote registra todos no `registry`."""

from __future__ import annotations

from . import choice, numbers, person
from .base import Context, Job, Provider, Run

__all__ = ["Context", "Job", "Provider", "Run", "choice", "numbers", "person"]
