from __future__ import annotations

import numpy as np
import pytest

pl = pytest.importorskip("polars")

from nini_datagen.core.arrow import bits_to_series, concat, numeric_to_series, views_to_series  # noqa: E402

from .test_views import STRINGS, make_views  # noqa: E402


def test_views_to_series():
    V, D = make_views(STRINGS)
    s = views_to_series(V, D, "col")
    assert s.name == "col"
    assert s.dtype == pl.String
    assert s.to_list() == [x.decode() for x in STRINGS]


def test_views_to_series_inline_only():
    V, _ = make_views([b"a", b"bc"])
    assert views_to_series(V, None, "c").to_list() == ["a", "bc"]


def test_views_to_series_validation():
    with pytest.raises(ValueError, match="uint32"):
        views_to_series(np.zeros((2, 4), np.int32), None, "c")


def test_bits_to_series():
    bits = np.packbits(np.array([1, 0, 1, 1, 0, 0, 0, 1, 1], np.uint8), bitorder="little")
    assert bits_to_series(bits, 9, "b").to_list() == [True, False, True, True, False, False, False, True, True]
    with pytest.raises(ValueError, match="insuficientes"):
        bits_to_series(bits, 17, "b")


def test_numeric_and_concat():
    a = numeric_to_series(np.arange(3, dtype=np.int64), "n")
    b = numeric_to_series(np.arange(3, 5, dtype=np.int64), "n")
    out = concat([a, b], "n", pl.Int64)
    assert out.to_list() == [0, 1, 2, 3, 4]
    assert out.n_chunks() == 2  # sem rechunk
    assert concat([], "n", pl.Int64).dtype == pl.Int64
    assert concat([a], "n", pl.Int64) is a
