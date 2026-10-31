from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from nini_datagen.core.tables import Vocabulary, alias_table, check_weights
from nini_datagen.core.views import decode


def test_vocabulary_roundtrip():
    strings = ["", "a", "exatamente12", "treze letras!", "Conceição", "x" * 300]
    v = Vocabulary.from_strings(strings)
    assert len(v) == len(strings)
    assert decode(v.views, v.data) == [s.encode() for s in strings]
    assert not v.views.flags.writeable
    sub = v.slice(3, 5)
    assert decode(sub.views, sub.data) == [s.encode() for s in strings[3:5]]


def test_vocabulary_without_long_strings():
    v = Vocabulary.from_strings(["F", "M"])
    assert v.data is None
    assert decode(v.views) == [b"F", b"M"]


def test_vocabulary_errors():
    with pytest.raises(ValueError, match="vazio"):
        Vocabulary.from_strings([])
    with pytest.raises(TypeError, match="texto"):
        Vocabulary.from_strings(["a", 1])  # type: ignore[list-item]


def test_alias_table_and_weights():
    t = alias_table([1, 2, 3])
    assert t.dtype == np.uint64
    assert t.shape == (3,)
    bad_cases: list[Any] = [[], [1, -1], [0, 0], [1, float("nan")], [[1, 2]]]
    for bad in bad_cases:
        with pytest.raises(ValueError, match="weights"):
            check_weights(bad)
    with pytest.raises(ValueError, match="3 opções"):
        check_weights([1, 2], 3)
