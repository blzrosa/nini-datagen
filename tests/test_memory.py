"""Buffers grandes do pool de memória do Arrow (`core.memory.empty`)."""

from __future__ import annotations

import gc

import numpy as np
import polars as pl
import pyarrow as pa
import pytest

from nini_datagen.core.memory import POOL_ENV, POOL_MIN_BYTES, empty


def test_small_is_plain_numpy() -> None:
    a = empty((10, 4), np.uint32)
    assert a.shape == (10, 4)
    assert a.dtype == np.uint32
    assert a.base is None


def test_large_comes_from_arrow_pool_and_is_writable() -> None:
    pool = pa.default_memory_pool()
    before = pool.bytes_allocated()
    n = POOL_MIN_BYTES // 4 + 1000
    a = empty((n, 4), np.uint32)
    assert a.shape == (n, 4)
    assert a.flags.c_contiguous
    assert a.flags.writeable
    assert isinstance(a.base, (pa.Buffer, np.ndarray))
    assert pool.bytes_allocated() - before >= a.nbytes
    a[:] = 7
    assert int(a.sum()) == 7 * a.size


def test_buffer_lives_with_the_series() -> None:
    n = POOL_MIN_BYTES  # int64: 8 MB
    a = empty(n, np.int64)
    a[:] = np.arange(n)
    s = pl.Series("x", a)
    del a
    gc.collect()
    assert s[-1] == n - 1
    assert s.sum() == n * (n - 1) // 2


def test_env_turns_pool_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(POOL_ENV, "0")
    a = empty(POOL_MIN_BYTES, np.uint8)
    assert a.base is None
