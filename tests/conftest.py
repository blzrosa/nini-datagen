from __future__ import annotations

import numpy as np
import pytest

from nini_datagen import _native
from nini_datagen.core.rng import seed_state


@pytest.fixture(scope="session")
def lib():
    return _native.lib()


@pytest.fixture
def state():
    """Estado novo do xoshiro (4 x uint64) para chamar um kernel direto."""
    return seed_state(12345, "tests")


@pytest.fixture
def P():
    return _native.ptr


def as_str(rows: list[bytes]) -> list[str]:
    return [r.decode("utf-8") for r in rows]


def digits(s: str) -> list[int]:
    return [ord(c) - 48 for c in s if c.isalnum()]


def u8(n: int) -> np.ndarray:
    return np.zeros(n, np.uint8)


if getattr(__import__("polars"), "IS_FAKE", False):  # sem o Polars de verdade não dá para ler o CNEFE em Parquet
    from .address_fixture import install

    install()


def pytest_addoption(parser):
    parser.addoption(
        "--record-golden",
        action="store_true",
        default=False,
        help="grava (sobrescreve) os gabaritos em tests/golden/ em vez de comparar",
    )
