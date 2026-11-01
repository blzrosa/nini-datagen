"""Buffers grandes do pool de memória do C++ (`core.memory.empty`)."""

from __future__ import annotations

import gc

import numpy as np
import polars as pl
import pytest

import nini_datagen as dg
from nini_datagen.core.memory import POOL_ENV, POOL_MIN_BYTES, empty, pool_limit, pool_stats, release_memory


def test_small_is_plain_numpy() -> None:
    a = empty((10, 4), np.uint32)
    assert a.shape == (10, 4)
    assert a.dtype == np.uint32
    assert a.base is None


def test_large_comes_from_pool_and_returns_to_it() -> None:
    gc.collect()
    before = pool_stats()
    n = POOL_MIN_BYTES // 4 + 1000
    a = empty((n, 4), np.uint32)
    assert a.shape == (n, 4)
    assert a.flags.c_contiguous
    assert a.flags.writeable
    assert a.base is not None
    assert pool_stats()["in_use"] >= before["in_use"] + a.nbytes
    a[:] = 7
    assert int(a.sum()) == 7 * a.size
    del a
    gc.collect()
    after = pool_stats()
    assert after["in_use"] == before["in_use"]
    b = empty((n, 4), np.uint32)  # o mesmo tamanho: sai do que foi guardado
    assert pool_stats()["hits"] > after["hits"]
    del b


def test_slice_keeps_block_alive() -> None:
    a = empty(POOL_MIN_BYTES, np.int64)
    a[:] = np.arange(len(a))
    part = a[-10:]
    del a
    gc.collect()
    assert part.tolist() == list(range(POOL_MIN_BYTES - 10, POOL_MIN_BYTES))


def test_buffer_lives_with_the_series() -> None:
    n = POOL_MIN_BYTES  # int64: 8 MB
    a = empty(n, np.int64)
    a[:] = np.arange(n)
    s = pl.Series("x", a)
    del a
    gc.collect()
    assert s[-1] == n - 1
    assert s.sum() == n * (n - 1) // 2


def test_tables_reuse_pool_and_release_memory() -> None:
    g = dg.DataGen(seed=3)
    schema = {"cpf": "cpf", "nome": "full_name", "x": "uniform", "obs": "sentence"}
    first = g.table(200_000, schema)
    del first
    gc.collect()
    hits = pool_stats()["hits"]
    second = g.table(200_000, schema)
    assert pool_stats()["hits"] > hits
    assert second.height == 200_000
    del second
    gc.collect()
    release_memory()
    assert pool_stats()["cached"] == 0


def test_limit() -> None:
    old = pool_limit()
    try:
        assert pool_limit(0) == 0
        a = empty(POOL_MIN_BYTES, np.uint8)
        del a
        gc.collect()
        assert pool_stats()["cached"] == 0  # limite 0: nada fica guardado
    finally:
        pool_limit(old)
    assert pool_limit() == old


@pytest.mark.parametrize("mode", ["0", "arrow"])
def test_env_modes(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    if mode == "arrow":
        pytest.importorskip("pyarrow")
    monkeypatch.setenv(POOL_ENV, mode)
    a = empty(POOL_MIN_BYTES, np.uint8)
    a[:] = 1
    if mode == "0":
        assert a.base is None
    else:
        assert a.base is not None
