"""Base de endereços sintética, no mesmo formato da real (para rodar os testes sem o CNEFE, ex. com o Polars falso).

8 municípios de 4 UFs e 300 trechos: nomes curtos e longos (com e sem acento), trechos com e sem faixa de números e
sem bairro (vira "Centro"), coordenadas com 3 casas.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from nini_datagen.locales import AddressBase, Municipalities
from nini_datagen.locales.pt_BR import PtBR

CITIES = [  # código IBGE, nome, UF, população
    (1302603, "Manaus", "AM", 2_063_689),
    (3106200, "Belo Horizonte", "MG", 2_315_560),
    (3170206, "Uberlândia", "MG", 713_224),
    (3303302, "Niterói", "RJ", 481_749),
    (3304557, "Rio de Janeiro", "RJ", 6_211_223),
    (3509502, "Campinas", "SP", 1_139_047),
    (3548500, "Santos", "SP", 418_608),
    (3550308, "São Paulo", "SP", 11_451_999),
]
STREETS = [
    "Rua A", "Rua das Flores", "Avenida Paulista", "Rua XV de Novembro", "Travessa São João", "Alameda Santos",
    "Avenida Presidente Juscelino Kubitschek de Oliveira", "Rua Conceição", "Estrada do Açude", "Praça da Sé",
]  # fmt: skip
DISTRICTS = ["Bela Vista", "Jardim Paulista", "Copacabana", "Savassi", "Adrianópolis", "Gonzaga", "Icaraí", "Cambuí"]


def municipalities() -> Municipalities:
    return Municipalities(
        ids=np.array([c[0] for c in CITIES], np.int32),
        names=tuple(c[1] for c in CITIES),
        ufs=tuple(c[2] for c in CITIES),
        population=np.array([c[3] for c in CITIES], np.float64),
    )


def addresses(source: str = "lite") -> AddressBase:
    r = np.random.default_rng(7)
    n = 300
    city = r.integers(0, len(CITIES), n).astype(np.uint32)
    cep = np.array([1000, 30000, 38400, 24000, 20000, 13000, 11000, 1000])[city] * 1000 + r.integers(0, 1000, n)
    lo = np.where(np.arange(n) % 2 == 0, r.integers(1, 50, n), 0).astype(np.int32)
    hi = np.where(lo > 0, lo + r.integers(0, 2000, n), 0).astype(np.int32)
    district = r.integers(0, len(DISTRICTS) + 1, n).astype(np.uint32)  # == len: sem bairro -> "Centro"
    return AddressBase(
        source=source,
        cep=cep.astype(np.uint32),
        city=city,
        street=r.integers(0, len(STREETS), n).astype(np.uint32),
        district=district,
        weight=r.integers(1, 500, n).astype(np.float64),
        streets=pl.Series("street", STREETS),
        districts=pl.Series("district", [*DISTRICTS, "Centro"]),
        number_min=lo if source == "full" else None,
        number_max=hi if source == "full" else None,
        lat=(-23_550 + r.integers(-500, 500, n)).astype(np.int32),
        lon=(-46_633 + r.integers(-500, 500, n)).astype(np.int32),
        coord_scale=1000.0,
    )


def install() -> None:
    """Troca as bases do pt_BR pelas sintéticas (só nos testes com o Polars falso)."""

    def _mun(self: PtBR) -> Municipalities:
        return self.cached("municipalities", municipalities)

    def _addr(self: PtBR, source: str = "auto") -> AddressBase:
        if source not in ("auto", "full", "lite"):
            raise ValueError("source deve ser 'auto', 'full' ou 'lite'")
        kind = "full" if source == "full" else "lite"
        return self.cached(("addresses", kind), lambda: addresses(kind))

    PtBR.municipalities = _mun  # type: ignore[method-assign]
    PtBR.addresses = _addr  # type: ignore[method-assign]
