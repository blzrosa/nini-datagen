from __future__ import annotations

import unicodedata

import numpy as np
import pytest

from nini_datagen.locales import available, get_locale


def test_available_and_singleton():
    assert available() == ["pt_BR"]
    assert get_locale("pt_BR") is get_locale()
    assert get_locale(get_locale()) is get_locale()
    with pytest.raises(ValueError, match="pt_BR"):
        get_locale("en_US")
    assert "pt_BR" in repr(get_locale())


def test_first_names_data():
    d = get_locale().first_names()
    assert len(d.names) > 1500
    assert len(set(d.names)) == len(d.names)
    for arr in (d.total, d.female, d.male):
        assert arr.shape == (len(d.names),)
        assert (arr >= 0).all()
    assert d.names[0] == "Maria"
    assert d.female.sum() > 0
    assert d.male.sum() > 0
    for x in d.names:
        assert x == unicodedata.normalize("NFC", x)
        assert x == x.strip()
        assert x[0].isupper(), x
        assert " " not in x, x  # o IBGE conta só o primeiro nome
    spelled = dict(zip(d.names, d.total, strict=True))
    for name in ("José", "João", "Antônio", "Luís", "Sebastião", "Gláucia", "Léo", "Iva"):
        assert name in spelled, name
    for wrong in ("Ivã", "Glaúcia", "Jésus", "Leo", "Joséfa", "Tamára", "Nélson"):
        assert wrong not in spelled, wrong


def test_last_names_data():
    d = get_locale().last_names()
    assert len(d.names) > 5000
    assert len(set(d.names)) == len(d.names)
    assert (d.weights > 0).all()
    assert d.names[:3] == ("Silva", "Santos", "Oliveira")
    assert "de Jesus" in d.names
    assert all(x == unicodedata.normalize("NFC", x) for x in d.names)


def test_age_weights_shape():
    w = get_locale().age_weights(0, 100)
    assert w.shape == (101,)
    assert (w > 0).all()
    assert np.isclose(w[:40], 1.0).all()
    assert w[90] < w[50] < w[30]
    assert get_locale().age_weights(5, 5).shape == (1,)


def test_cache_builds_once():
    loc = get_locale()
    calls = []
    a = loc.cached(("teste", 1), lambda: calls.append(1) or object())
    b = loc.cached(("teste", 1), lambda: calls.append(1) or object())
    assert a is b
    assert len(calls) == 1


def test_compound_prefixes_exist_with_right_sex():
    loc = get_locale()
    d = loc.first_names()
    pos = {x: i for i, x in enumerate(d.names)}
    fem, mas = loc.compound_prefixes()
    assert "Maria" in fem
    assert "João" in mas
    assert all(d.female[pos[x]] > 0 for x in fem)
    assert all(d.male[pos[x]] > 0 for x in mas)


def test_states_population_and_area_codes():
    states = get_locale().states()
    assert len(states) == 27
    assert sum(s.population for s in states.values()) == 203_080_756  # Censo 2022 (IBGE)
    codes = [d for s in states.values() for d in s.area_codes]
    assert len(codes) == len(set(codes)) == 67  # os 67 DDDs, cada um numa UF só
    assert all(11 <= d <= 99 and d % 10 != 0 for d in codes)


def test_small_lists():
    loc = get_locale()
    sectors, brands, types = loc.company_parts()
    assert len(set(sectors)) == len(sectors)
    assert len(set(brands)) == len(brands)
    assert types.names[0] == "LTDA"
    v = loc.vehicles()
    assert len(v.models) == len(v.brands.names)
    assert len(set(loc.occupations())) == len(loc.occupations())
    common, themes = loc.grammar()
    assert all("frase" in t for t in themes.values())
    assert {"d", "valor", "tempo"} <= set(common)
