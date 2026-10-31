"""nini-datagen: dados sintéticos realistas do Brasil em escala, gerados por kernels C++ direto em Polars.

A v0.2.0 está sendo montada por fases (veja CHANGELOG.md). Nesta etapa existem o núcleo (biblioteca C++, sementes,
blocos e buffers); os geradores públicos (``cpf``, ``cnpj``, ``name``, ``address``...) e ``table``/``scan`` entram nas
próximas fases.
"""

from __future__ import annotations

from importlib import metadata

from .errors import DatagenError, NativeLibraryError

try:
    __version__ = metadata.version("nini-datagen")
except metadata.PackageNotFoundError:  # rodando de uma cópia sem instalar
    __version__ = "0.0.0"

__all__ = ["DatagenError", "NativeLibraryError", "__version__"]
