"""Endereços (CNEFE), CEP, cidade e UF; leitura da base e download de `datasets`."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

import nini_datagen as dg
from nini_datagen import datasets
from nini_datagen.locales import get_locale
from nini_datagen.locales.pt_BR import _load_cnefe

N = 100_000
LOC = get_locale()


def base_rows(source: str = "auto"):
    b = LOC.addresses(source)
    mun = LOC.municipalities()
    return b, mun


# ------------------------------------------------------------------ CEP
def test_cep_formats_and_weights():
    ceps = dg.cep(N, seed=1).to_list()
    assert all(re.fullmatch(r"\d{5}-\d{3}", c) for c in ceps)
    plain = dg.cep(N, seed=1, formatted=False).to_list()
    assert [c.replace("-", "") for c in ceps] == plain
    b, _ = base_rows()
    known = {f"{c:08d}" for c in b.cep.tolist()}
    assert set(plain) <= known
    # o CEP de maior peso (somando os trechos dele) sai na proporção do peso
    ceps_u, inv = np.unique(b.cep, return_inverse=True)
    w = np.bincount(inv, weights=b.weight)
    top = int(np.argmax(w))
    expected = N * w[top] / w.sum()
    got = Counter(plain)[f"{int(ceps_u[top]):08d}"]
    assert abs(got - expected) <= 5 * expected**0.5 + 5, (got, expected)


def test_cep_by_uf():
    b, mun = base_rows()
    ufs = np.array(mun.ufs)[b.city]
    sp = {f"{c:08d}" for c in b.cep[ufs == "SP"].tolist()}
    got = set(dg.cep(5000, seed=2, uf="sp", formatted=False).to_list())
    assert got <= sp
    with pytest.raises(ValueError, match="UF desconhecida"):
        dg.cep(10, seed=1, uf="XX")
    with pytest.raises(ValidationError, match="sigla"):
        dg.CepConfig.model_validate({"uf": "São Paulo"})


# ------------------------------------------------------------------ endereço
FIELDS = ["street", "number", "complement", "neighborhood", "city", "state", "cep"]


def test_address_fields_are_consistent():
    s = dg.address(N, seed=1)
    df = s.struct.unnest()
    assert df.columns == FIELDS
    b, mun = base_rows()
    streets = set(b.streets.to_list())
    districts = set(b.districts.to_list())
    city_uf = {(n, u) for n, u in zip(mun.names, mun.ufs, strict=True)}
    rows = list(zip(*(df[c].to_list() for c in FIELDS), strict=True))
    for street, number, _, nb, city, uf, cep in rows[:20_000]:
        assert street in streets
        assert nb in districts
        assert (city, uf) in city_uf
        assert re.fullmatch(r"\d{5}-\d{3}", cep)
        assert 1 <= number <= 99_999
    # rua, bairro, cidade, UF e CEP saem do MESMO trecho: cada combinação existe na base
    combos = {
        (b.streets[int(s_)], b.districts[int(d)], mun.names[int(c)], f"{int(z) // 1000:05d}-{int(z) % 1000:03d}")
        for s_, d, c, z in zip(b.street, b.district, b.city, b.cep, strict=True)
    }
    assert all((r[0], r[3], r[4], r[6]) in combos for r in rows[:20_000])


def test_address_complement_share_and_numbers():
    df = dg.address(N, seed=3, complement=0.4).struct.unnest()
    share = 1 - df["complement"].null_count() / N
    assert abs(share - 0.4) < 0.01
    assert set(df["complement"].drop_nulls().to_list()) <= set(LOC.address_complements())
    nums = np.array(df["number"].to_list())
    assert nums.min() >= 1
    assert np.median(nums) < 200  # números baixos são mais comuns
    assert dg.address(1000, seed=3, complement=0).struct.unnest()["complement"].null_count() == 1000


def test_address_number_within_street_range_on_full_base():
    try:
        b = LOC.addresses("full")
    except datasets.DatasetError:
        pytest.skip("precisa da base completa (datasets.download('cnefe'))")
    if b.number_min is None or b.number_max is None:
        pytest.skip("a base não tem faixa de números")
    ranges: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for s_, z, lo, hi in zip(b.street, b.cep, b.number_min, b.number_max, strict=True):
        key = (b.streets[int(s_)], f"{int(z) // 1000:05d}-{int(z) % 1000:03d}")
        ranges.setdefault(key, []).append((int(lo), int(hi)))
    df = dg.address(20_000, seed=4, source="full").struct.unnest()
    for st, cep, num in zip(df["street"].to_list(), df["cep"].to_list(), df["number"].to_list(), strict=True):
        opts = ranges[(st, cep)]
        assert any(lo <= num <= hi for lo, hi in opts if lo > 0) or any(lo <= 0 for lo, _ in opts), (st, cep, num)


def test_address_optional_fields():
    s = dg.address(20_000, seed=5, phone=True, coords=True, full=True)
    df = s.struct.unnest()
    assert df.columns == [*FIELDS, "phone", "latitude", "longitude", "full"]
    states = LOC.states()
    phones, ufs = df["phone"].to_list(), df["state"].to_list()
    assert all(re.fullmatch(r"\(\d\d\) 9?\d{4}-\d{4}", p) for p in phones)
    assert all(int(p[1:3]) in states[u].area_codes for p, u in zip(phones, ufs, strict=True))
    lat, lon = np.array(df["latitude"].to_list()), np.array(df["longitude"].to_list())
    assert ((lat > -34) & (lat < 6)).all()  # território brasileiro
    assert ((lon > -74) & (lon < -28)).all()
    parts = [df[c].to_list() for c in ["street", "number", "neighborhood", "city", "state", "cep"]]
    for f, (st, num, nb, city, uf, cep) in zip(df["full"].to_list(), zip(*parts, strict=True), strict=True):
        assert f == f"{st}, {num} - {nb}, {city} - {uf}, {cep}"


def test_address_by_uf_and_errors():
    df = dg.address(5000, seed=6, uf=["RJ", "mg"]).struct.unnest()
    assert set(df["state"].to_list()) <= {"RJ", "MG"}
    with pytest.raises(ValueError, match="UF desconhecida"):
        dg.address(10, seed=1, uf="ZZ")
    with pytest.raises(ValidationError):
        dg.AddressConfig(complement=1.5)


# ------------------------------------------------------------------ cidade e UF
def test_city_and_state():
    mun = LOC.municipalities()
    cities = Counter(dg.city(N, seed=1).to_list())
    assert set(cities) <= set(mun.names)
    biggest = mun.names[int(np.argmax(mun.population))]
    assert cities.most_common(1)[0][0] == biggest
    sp = dg.city(5000, seed=1, uf="SP", with_state=True).to_list()
    assert all(c.endswith("/SP") for c in sp)
    st = Counter(dg.state(N, seed=1).to_list())
    assert set(st) <= set(LOC.states())
    assert st.most_common(1)[0][0] == "SP"
    flat = Counter(dg.state(N, seed=1, weighted=False).to_list())
    assert len(flat) == 27
    assert max(flat.values()) / min(flat.values()) < 1.3


# ------------------------------------------------------------------ leitura da base (formato em disco)
def test_load_cnefe_folder(tmp_path: Path):
    pl = pytest.importorskip("polars")
    if getattr(pl, "IS_FAKE", False):
        pytest.skip("precisa do Polars de verdade (Parquet)")
    mun = LOC.municipalities()
    ids = mun.ids[:3]
    pl.DataFrame({
        "cep": pl.Series([1310100, 20040002, 30130010], dtype=pl.UInt32),
        "city_id": pl.Series(ids.tolist(), dtype=pl.Int32),
        "street": pl.Series([0, 1, 1], dtype=pl.UInt32),
        "district": pl.Series([0, None, 0], dtype=pl.UInt32),
        "number_min": pl.Series([1, None, 5], dtype=pl.Int32),
        "number_max": pl.Series([500, 80, 1_545_883_042], dtype=pl.Int32),
        "lat": pl.Series([-23561, None, -19920], dtype=pl.Int32),
        "lon": pl.Series([-46656, -43176, -43938], dtype=pl.Int32),
        "weight": pl.Series([10, 20, 30], dtype=pl.UInt32),
    }).write_parquet(tmp_path / "addresses.parquet")  # fmt: skip
    pl.DataFrame({"name": ["Avenida Paulista", "Rua da Conceição"]}).write_parquet(tmp_path / "streets.parquet")
    pl.DataFrame({"name": ["Bela Vista"]}).write_parquet(tmp_path / "districts.parquet")
    (tmp_path / "format.json").write_text(json.dumps({"format": 1, "coord_scale": 1000}))
    b = _load_cnefe(tmp_path, "teste", mun)
    assert b.districts.to_list() == ["Bela Vista", "Centro"]
    assert b.district.tolist() == [0, 1, 0]  # sem bairro -> "Centro" (o último)
    assert b.city.tolist() == [0, 1, 2]
    # faixa nula ou absurda vira "sem faixa" (0); coordenada nula vira a média do município (aqui, o único trecho)
    assert b.number_min is not None
    assert b.number_max is not None
    assert b.number_min.tolist() == [1, 0, 0]
    assert b.number_max.tolist() == [500, 0, 0]
    assert b.lat is not None
    assert b.lat.tolist() == [-23561, 0, -19920]
    assert b.coord_scale == 1000
    (tmp_path / "format.json").write_text(json.dumps({"format": 99}))
    with pytest.raises(ValueError, match="formato"):
        _load_cnefe(tmp_path, "teste", mun)


def test_lite_base_ships_with_the_package():
    pl = pytest.importorskip("polars")
    if getattr(pl, "IS_FAKE", False):
        pytest.skip("precisa do Polars de verdade (Parquet)")
    b = LOC.addresses("lite")
    mun = LOC.municipalities()
    # todo município do CNEFE 2022 tem pelo menos um trecho; a lista do IBGE pode ter municípios criados depois do
    # Censo (ex.: Boa Esperança do Norte/MT, instalado em 2025), que não têm endereço no CNEFE
    covered = len(set(b.city.tolist()))
    assert covered >= 5570
    assert len(mun.ids) - covered <= 5
    assert b.number_min is None
    assert b.coord_scale == 1000


# ------------------------------------------------------------------ datasets
def make_zip(tmp_path: Path, members: dict[str, bytes]) -> tuple[Path, str]:
    z = tmp_path / "base.zip"
    with zipfile.ZipFile(z, "w") as f:
        for name, data in members.items():
            f.writestr(name, data)
    return z, hashlib.sha256(z.read_bytes()).hexdigest()


@pytest.fixture
def fake_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NINI_DATAGEN_CACHE", str(tmp_path / "cache"))

    def use(url: str, sha: str) -> None:
        ds = datasets.Dataset("cnefe", "teste", 1, 1, url, sha, 0)
        monkeypatch.setattr(datasets, "_manifest", lambda: {"cnefe": ds})

    return use


def test_download_verifies_and_caches(tmp_path: Path, fake_manifest):
    z, sha = make_zip(tmp_path, {"format.json": b'{"format": 1}', "addresses.parquet": b"x"})
    fake_manifest(z.as_uri(), sha)
    assert datasets.path("cnefe") is None
    out = datasets.download("cnefe")
    assert (out / "format.json").read_bytes() == b'{"format": 1}'
    assert datasets.path("cnefe") == out
    z.unlink()  # já está no cache: não baixa de novo
    assert datasets.download("cnefe") == out


def test_download_rejects_bad_files(tmp_path: Path, fake_manifest):
    z, _ = make_zip(tmp_path, {"a.txt": b"1"})
    fake_manifest(z.as_uri(), "0" * 64)
    with pytest.raises(datasets.DatasetError, match="corrompido"):
        datasets.download("cnefe")
    assert datasets.path("cnefe") is None
    evil, sha_evil = make_zip(tmp_path, {"../fora.txt": b"1"})
    fake_manifest(evil.as_uri(), sha_evil)
    with pytest.raises(datasets.DatasetError, match="suspeito"):
        datasets.download("cnefe")
    assert not (tmp_path / "cache" / ".." / "fora.txt").exists()
    fake_manifest(z.as_uri(), "")
    with pytest.raises(datasets.DatasetError, match="publicada"):
        datasets.download("cnefe")
    with pytest.raises(ValueError, match="desconhecida"):
        datasets.get("nada")
