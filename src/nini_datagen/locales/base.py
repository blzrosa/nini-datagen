"""Interface de um locale: os dados e as regras de um país, pedidos pelos providers (que não leem arquivos)."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, TypeVar

import numpy as np

__all__ = ["FirstNames", "Locale", "WeightedNames"]

T = TypeVar("T")


@dataclass(frozen=True, eq=False)
class FirstNames:
    """Primeiros nomes com frequência: ``total`` (todas as pessoas), ``female`` e ``male`` (por sexo)."""

    names: tuple[str, ...]
    total: np.ndarray
    female: np.ndarray
    male: np.ndarray


@dataclass(frozen=True, eq=False)
class WeightedNames:
    names: tuple[str, ...]
    weights: np.ndarray


class Locale(ABC):
    """Fonte dos dados de um país. Cada locale é carregado uma vez (preguiçoso) e compartilhado entre threads.

    ``cached(chave, fábrica)`` guarda estruturas derivadas (vocabulários, tabelas alias) para que cada uma seja montada
    uma vez só por processo.
    """

    code: ClassVar[str]

    def __init__(self) -> None:
        self._cache: dict[Any, Any] = {}
        self._lock = threading.RLock()  # reentrante: uma fábrica pode pedir outro item do cache

    def cached(self, key: Any, factory: Callable[[], T]) -> T:
        try:
            return self._cache[key]
        except KeyError:
            pass
        with self._lock:
            if key not in self._cache:
                self._cache[key] = factory()
            return self._cache[key]

    @property
    @abstractmethod
    def p_female(self) -> float:
        """Fração de mulheres na população."""

    @abstractmethod
    def first_names(self) -> FirstNames: ...

    @abstractmethod
    def last_names(self) -> WeightedNames: ...

    @abstractmethod
    def compound_prefixes(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """(femininos, masculinos): nomes que costumam abrir um prenome composto."""

    @abstractmethod
    def age_weights(self, low: int, high: int) -> np.ndarray:
        """Um peso por idade, de ``low`` a ``high``."""

    def __repr__(self) -> str:
        return f"<Locale {self.code}>"
