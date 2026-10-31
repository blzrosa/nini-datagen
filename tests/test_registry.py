from __future__ import annotations

import pytest

import nini_datagen as dg
from nini_datagen.registry import Registry, registry

PHASE3 = {
    "age",
    "boolean",
    "choice",
    "date",
    "datetime",
    "first_name",
    "full_name",
    "integer",
    "last_name",
    "lognormal",
    "normal",
    "sex",
    "uniform",
}


def test_all_kinds_registered():
    assert set(registry.kinds()) >= PHASE3
    assert dg.DataGen.kinds() == registry.kinds()
    assert "integer" in registry


def test_every_kind_has_shortcuts():
    g = dg.DataGen(seed=0)
    for kind in registry.kinds():
        assert callable(getattr(g, kind)), kind
        assert callable(getattr(dg, kind)), kind
        assert getattr(dg, kind).__name__ == kind


def test_unknown_kind_suggests():
    with pytest.raises(KeyError, match="first_name"):
        registry.get("firstname")
    with pytest.raises(KeyError, match="Disponíveis"):
        dg.generate("nada", 3)


def test_double_registration_is_an_error():
    r = Registry()
    cls = type(registry.get("integer"))
    r.register(cls)
    with pytest.raises(ValueError, match="já está registrado"):
        r.register(cls)
