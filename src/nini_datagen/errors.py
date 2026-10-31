"""Exceções do nini-datagen."""

from __future__ import annotations


class DatagenError(Exception):
    """Base de todos os erros do nini-datagen."""


class NativeLibraryError(DatagenError, ImportError):
    """A biblioteca C++ (libdatagen) não foi encontrada, não carregou ou tem ABI diferente do pacote Python."""
