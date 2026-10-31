"""Interface de um locale: os dados e as regras de um país, pedidos pelos providers (que não leem arquivos)."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, TypeVar

import numpy as np

__all__ = ["AddressBase", "FirstNames", "Grammar", "Locale", "Municipalities", "State", "Vehicles", "WeightedNames"]

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


@dataclass(frozen=True)
class State:
    """Unidade da federação: nome, população e códigos de área (DDD) do telefone."""

    name: str
    population: int
    area_codes: tuple[int, ...]


@dataclass(frozen=True)
class Vehicles:
    """Marcas com peso e, para cada marca, modelos com peso (``models[i]`` são os modelos de ``brands.names[i]``)."""

    brands: WeightedNames
    models: tuple[WeightedNames, ...]


@dataclass(frozen=True, eq=False)
class Municipalities:
    """Municípios: código IBGE, nome, UF (sigla) e população, alinhados por posição."""

    ids: np.ndarray  # int32
    names: tuple[str, ...]
    ufs: tuple[str, ...]
    population: np.ndarray  # float64


@dataclass(frozen=True, eq=False)
class AddressBase:
    """Trechos de rua (CEP x logradouro) com peso, alinhados por posição.

    ``city`` indexa `Municipalities`; ``street`` e ``district`` indexam ``streets`` e ``districts`` (Series String; o
    último bairro é o usado quando o trecho não tem bairro). ``number_min``/``number_max``: faixa real dos números do
    trecho (None na base leve). ``lat``/``lon``: coordenadas inteiras (graus x ``coord_scale``) ou None.
    """

    source: str
    cep: np.ndarray  # uint32
    city: np.ndarray  # uint32
    street: np.ndarray  # uint32
    district: np.ndarray  # uint32
    weight: np.ndarray  # float64
    streets: Any
    districts: Any
    number_min: np.ndarray | None = None  # int32
    number_max: np.ndarray | None = None
    lat: np.ndarray | None = None  # int32
    lon: np.ndarray | None = None
    coord_scale: float = 1.0

    def __len__(self) -> int:
        return len(self.cep)


# Gramática de frases: símbolo -> opções; opção = texto (peso 1) ou (texto, peso), com {símbolo} para expandir
Grammar = dict[str, list[Any]]


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

    @abstractmethod
    def url_words(self) -> tuple[str, ...]:
        """Palavras ASCII (minúsculas, até 24 letras) para domínios e caminhos de URL."""

    @abstractmethod
    def top_level_domains(self) -> WeightedNames:
        """Domínios de topo (sem o ponto inicial: ``"com.br"``) com peso."""

    @abstractmethod
    def states(self) -> dict[str, State]:
        """Unidades da federação por sigla."""

    @abstractmethod
    def email_domains(self) -> WeightedNames: ...

    @abstractmethod
    def company_parts(self) -> tuple[tuple[str, ...], tuple[str, ...], WeightedNames]:
        """(ramos, marcas, tipos societários com peso) da razão social; os sobrenomes vêm de `last_names`."""

    @abstractmethod
    def vehicles(self) -> Vehicles: ...

    @abstractmethod
    def occupations(self) -> tuple[str, ...]:
        """Profissões, da mais para a menos comum."""

    @abstractmethod
    def grammar(self) -> tuple[Grammar, dict[str, Grammar]]:
        """(símbolos comuns, temas): cada tema tem a raiz ``"frase"`` e pode usar os símbolos comuns."""

    @abstractmethod
    def municipalities(self) -> Municipalities: ...

    @abstractmethod
    def address_complements(self) -> tuple[str, ...]:
        """Complementos de endereço (``"Apto 12"``, ``"Casa 3"``...)."""

    @abstractmethod
    def addresses(self, source: str = "auto") -> AddressBase:
        """Base de endereços: ``"full"`` (completa, baixada), ``"lite"`` (leve, no pacote) ou ``"auto"`` (a completa
        se já estiver baixada, senão a leve)."""

    def __repr__(self) -> str:
        return f"<Locale {self.code}>"
