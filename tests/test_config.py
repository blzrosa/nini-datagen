from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

import nini_datagen as dg
from nini_datagen.config.numbers import epoch
from nini_datagen.registry import registry


def test_extra_field_is_an_error():
    with pytest.raises(ValidationError, match="extra"):
        dg.IntegerConfig(lo=1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        dg.integer(5, seed=1, hihg=3)


def test_configs_are_frozen_and_hashable():
    c = dg.IntegerConfig(low=1, high=6)
    with pytest.raises(ValidationError):
        c.low = 2  # type: ignore[misc]
    assert hash(c) == hash(dg.IntegerConfig(low=1, high=6))
    assert hash(dg.ChoiceConfig.model_validate({"values": ["a", "b"], "weights": [1, 2]}))


@pytest.mark.parametrize(
    ("cls", "kwargs", "match"),
    [
        (dg.IntegerConfig, {"low": 5, "high": 4}, "high"),
        (dg.IntegerConfig, {"low": 0, "high": 2**40, "dtype": "int32"}, "int32"),
        (dg.IntegerConfig, {"low": -(2**63), "high": 2**63 - 1}, "grande demais"),
        (dg.IntegerConfig, {"high": 2**63}, "less than or equal"),
        (dg.UniformConfig, {"low": 1.0, "high": 1.0}, "high"),
        (dg.UniformConfig, {"high": float("inf")}, "finite"),
        (dg.NormalConfig, {"std": 0}, "greater than 0"),
        (dg.LognormalConfig, {"sigma": -1}, "greater than 0"),
        (dg.BooleanConfig, {"p": 1.5}, "less than or equal"),
        (dg.BaseConfig, {"null_fraction": -0.1}, "greater than or equal"),
        (dg.BaseConfig, {"name": ""}, "at least 1"),
        (dg.DateConfig, {"start": "2020-01-02", "end": "2020-01-01"}, "end"),
        (dg.DatetimeConfig, {"start": "2020-01-01", "end": "2020-01-01"}, "end"),
        (dg.DatetimeConfig, {"start": "1600-01-01", "unit": "ns"}, "1677"),
        (dg.ChoiceConfig, {"values": []}, "at least 1"),
        (dg.ChoiceConfig, {"values": ["a", "b"], "weights": [1]}, "2 opções"),
        (dg.ChoiceConfig, {"values": ["a"], "weights": [-1]}, ">= 0"),
        (dg.ChoiceConfig, {"values": ["a", "b"], "weights": [0, 0]}, "soma"),
        (dg.ChoiceConfig, {"values": ["a", 1]}, "values"),
        (dg.SexConfig, {"labels": ("X", "X")}, "diferentes"),
        (dg.SexConfig, {"p_female": 2}, "less than or equal"),
        (dg.AgeConfig, {"low": 10, "high": 5}, "high"),
        (dg.AgeConfig, {"low": 0, "high": 2, "weights": [1, 1]}, "3 opções"),
        (dg.FirstNameConfig, {"sex": "X"}, "'F' or 'M'"),
        (dg.FullNameConfig, {"two_surnames": -0.5}, "greater than or equal"),
    ],
)
def test_invalid_configs(cls, kwargs, match):
    with pytest.raises(ValidationError, match=match):
        cls(**kwargs)


def test_parsing_and_defaults():
    c = dg.DateConfig.model_validate({"start": "2020-02-01", "end": dt.date(2020, 3, 1)})
    assert c.start == dt.date(2020, 2, 1)
    d = dg.DatetimeConfig.model_validate({"start": "2020-01-01T12:00:00", "end": "2020-01-02"})
    assert d.start == dt.datetime(2020, 1, 1, 12)
    assert dg.IntegerConfig().resolved_dtype == "int32"
    assert dg.IntegerConfig(high=2**31).resolved_dtype == "int64"
    assert dg.IntegerConfig(dtype="int64").resolved_dtype == "int64"
    assert dg.ChoiceConfig.model_validate({"values": [1, 2]}).values == (1, 2)
    assert dg.ChoiceConfig.model_validate({"values": [True, False]}).values == (True, False)
    assert dg.ChoiceConfig.model_validate({"values": [1.5, 2]}).values == (1.5, 2.0)


def test_epoch_is_exact():
    t = dt.datetime(2262, 4, 11, 23, 47, 16, 854775)
    assert epoch(t, "us") == 9_223_372_036_854_775
    assert epoch(t, "ns") == 9_223_372_036_854_775_000
    assert epoch(dt.datetime(1969, 12, 31, 23, 59, 59, 999_999), "ms") == -1
    aware = dt.datetime(2000, 1, 1, tzinfo=dt.timezone(dt.timedelta(hours=-3)))
    assert epoch(aware, "us") == epoch(dt.datetime(2000, 1, 1, 3), "us")


def test_registry_config_sources():
    base = dg.IntegerConfig(low=1, high=6)
    assert registry.config("integer") == dg.IntegerConfig()
    assert registry.config("integer", base) is base
    assert registry.config("integer", base, high=10) == dg.IntegerConfig(low=1, high=10)
    assert registry.config("integer", {"low": 2}, high=3) == dg.IntegerConfig(low=2, high=3)
    assert registry.config("choice", ["a", "b"]) == dg.ChoiceConfig(values=("a", "b"))
    assert registry.config("choice", ("x",), weights=[1]).weights == (1.0,)
    with pytest.raises(TypeError, match="IntegerConfig"):
        registry.config("integer", dg.BooleanConfig())
    with pytest.raises(TypeError):
        registry.config("integer", [1, 2])  # integer não aceita valor posicional
    with pytest.raises(TypeError):
        registry.config("choice", "abc")  # texto não é lista de valores


def test_registry_config_from_numpy_and_series():
    np = pytest.importorskip("numpy")
    assert registry.config("choice", np.array([1, 2])).values == (1, 2)
    pl = pytest.importorskip("polars")
    assert registry.config("choice", pl.Series(["a", "b"])).values == ("a", "b")
