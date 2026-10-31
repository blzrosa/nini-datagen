"""Transformações de dados prontos: dados sujos (`dirty`) e duplicatas (`add_duplicates`)."""

from __future__ import annotations

from .dirty import apply_dirty, dirty
from .duplicates import add_duplicates

__all__ = ["add_duplicates", "apply_dirty", "dirty"]
