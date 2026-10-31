"""Documentos, códigos e identificadores de rede: formato e dígitos verificadores em 1 milhão de linhas.

As conferências em massa são vetorizadas (numpy, sobre a matriz de bytes dos textos) e seguem as regras oficiais
escritas de novo aqui, independentes do C++; os validadores públicos (`nini_datagen.validators`) são conferidos numa
amostra e contra casos conhecidos.
"""

from __future__ import annotations

import ipaddress
import re
from collections import Counter
from urllib.parse import urlsplit

import numpy as np
import pytest
from pydantic import ValidationError

import nini_datagen as dg
from nini_datagen import validators as val

N = 1_000_000
SAMPLE = 20_000


def chars(s, width: int) -> np.ndarray:
    """Textos de comprimento fixo -> matriz (n, width) de bytes; falha se algum tiver outro comprimento."""
    raw = s.to_list()
    assert all(len(x) == width for x in raw), f"comprimento diferente de {width}"
    return np.frombuffer("".join(raw).encode("ascii"), np.uint8).reshape(-1, width).astype(np.int64)


def digits(s, width: int) -> np.ndarray:
    m = chars(s, width)
    assert ((m >= 48) & (m <= 57)).all(), "caractere que não é dígito"
    return m - 48


def mod11_dv(d: np.ndarray, weights) -> np.ndarray:
    r = (d * np.asarray(weights)).sum(axis=1) % 11
    return np.where(r < 2, 0, 11 - r)


def strip(s) -> list[str]:
    return [re.sub(r"[.\-/ ]", "", x) for x in s.to_list()]


def check_sample(fn, s) -> None:
    bad = [x for x in s.head(SAMPLE).to_list() if not fn(x)]
    assert not bad, f"inválidos: {bad[:5]}"


# ------------------------------------------------------------------ validadores contra casos conhecidos
@pytest.mark.parametrize(
    ("fn", "good", "bad"),
    [
        (val.cpf, ["529.982.247-25", "52998224725", "111.444.777-35"], ["529.982.247-26", "111.111.111-11", "1234", 5]),
        (val.cnpj, ["11.222.333/0001-81", "11222333000181", "12.ABC.345/01DE-35"], ["11.222.333/0001-82", "1" * 14]),
        (val.pis, ["120.56465.12-6", "12056465126"], ["12056465123", "1205646512"]),
        (val.credit_card, ["4111 1111 1111 1111", "378282246310005"], ["4111 1111 1111 1112", "abc"]),
        (val.iban, ["BR15 0000 0000 0000 1093 2840 814P 2", "GB82WEST12345698765432"], ["GB82WEST12345698765433"]),
        (val.ean13, ["7891000315507", "4006381333931"], ["7891000315508", "789100031550"]),
        (val.rg, ["24.678.131-2", "24678131-2"], ["24.678.131-5", "2467813"]),
    ],
)
def test_validators_known_values(fn, good, bad):
    assert all(fn(x) for x in good), [x for x in good if not fn(x)]
    assert not any(fn(x) for x in bad), [x for x in bad if fn(x)]


# ------------------------------------------------------------------ CPF
def test_cpf_valid_million():
    s = dg.cpf(N, seed=1)
    d = digits(s, 11)
    dv1 = mod11_dv(d[:, :9], range(10, 1, -1))
    assert (dv1 == d[:, 9]).all()
    assert (mod11_dv(d[:, :10], range(11, 1, -1)) == d[:, 10]).all()
    check_sample(val.cpf, s)
    # todos os 10 dígitos aparecem em cada posição da base, sem viés grosseiro
    for col in range(9):
        counts = np.bincount(d[:, col], minlength=10)
        assert counts.min() > 0.09 * N


def test_cpf_formatted_is_the_same_number():
    plain = dg.cpf(50_000, seed=3)
    fmt = dg.cpf(50_000, seed=3, formatted=True)
    assert all(re.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}", x) for x in fmt.to_list())
    assert strip(fmt) == plain.to_list()


@pytest.mark.parametrize("threads", [1, 4])
def test_cpf_unique(threads):
    s = dg.DataGen(seed=7, threads=threads).cpf(N, unique=True)
    assert s.n_unique() == N
    d = digits(s, 11)
    assert (mod11_dv(d[:, :9], range(10, 1, -1)) == d[:, 9]).all()
    assert (mod11_dv(d[:, :10], range(11, 1, -1)) == d[:, 10]).all()


def test_cpf_unique_prefix_and_limit():
    a = dg.cpf(1_000, seed=9, unique=True)
    b = dg.cpf(200_000, seed=9, unique=True)
    assert a.to_list() == b.head(1_000).to_list()
    # embaralhado: a diferença entre linhas vizinhas não é constante (era, na progressão afim)
    base = np.array([int(x[:9]) for x in b.to_list()], np.int64)
    assert len(np.unique(np.diff(base))) > 0.99 * (len(base) - 1)
    first = np.bincount(base // 10**8, minlength=10) / len(base)
    assert (np.abs(first - 0.1) < 0.005).all()
    with pytest.raises(ValueError, match="no máximo"):
        dg.cpf(10**9 + 1, seed=1, unique=True)


# ------------------------------------------------------------------ CNPJ
W1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
W2 = [6, *W1]


def cnpj_ok(m: np.ndarray) -> np.ndarray:
    v = m - 48
    dv1 = mod11_dv(v[:, :12], W1)
    dv2 = mod11_dv(np.column_stack([v[:, :12], dv1]), W2)
    return (dv1 == v[:, 12]) & (dv2 == v[:, 13])


def test_cnpj_valid_million():
    s = dg.cnpj(N, seed=1)
    m = chars(s, 14)
    assert ((m >= 48) & (m <= 57)).all()
    assert (m[:, 8:12] == np.frombuffer(b"0001", np.uint8)).all()
    assert cnpj_ok(m).all()
    check_sample(val.cnpj, s)


def test_cnpj_alphanumeric_and_branches():
    s = dg.cnpj(N, seed=2, alphanumeric=True, branch=None)
    m = chars(s, 14)
    alnum = ((m >= 48) & (m <= 57)) | ((m >= 65) & (m <= 90))
    assert alnum.all()
    assert ((m[:, 12:] >= 48) & (m[:, 12:] <= 57)).all(), "os DV são sempre numéricos"
    assert cnpj_ok(m).all()
    assert (m[:, :12] >= 65).mean() > 0.5, "letras deveriam ser maioria (26 de 36 símbolos)"
    assert len({x[8:12] for x in s.head(10_000).to_list()}) > 9_000
    check_sample(val.cnpj, s)
    fixed = dg.cnpj(1_000, seed=2, alphanumeric=True, branch="00A1")
    assert {x[8:12] for x in fixed.to_list()} == {"00A1"}


def test_cnpj_formatted_is_the_same_number():
    plain = dg.cnpj(50_000, seed=3, alphanumeric=True)
    fmt = dg.cnpj(50_000, seed=3, alphanumeric=True, formatted=True)
    assert all(re.fullmatch(r"[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-\d{2}", x) for x in fmt.to_list())
    assert strip(fmt) == plain.to_list()


@pytest.mark.parametrize("kw", [{}, {"alphanumeric": True}, {"branch": None}, {"alphanumeric": True, "branch": None}])
def test_cnpj_unique(kw):
    s = dg.DataGen(seed=11, threads=4).cnpj(N, unique=True, **kw)
    assert s.n_unique() == N
    assert cnpj_ok(chars(s, 14)).all()
    assert dg.cnpj(500, seed=11, unique=True, **kw).to_list() == s.head(500).to_list()


def test_cnpj_config_errors():
    with pytest.raises(ValidationError, match="alphanumeric"):
        dg.CNPJConfig(branch="00A1")
    with pytest.raises(ValidationError, match="0-9 e A-Z"):
        dg.CNPJConfig(branch="00a1", alphanumeric=True)
    with pytest.raises(ValidationError):
        dg.CNPJConfig(branch="001")
    with pytest.raises(ValueError, match="no máximo"):
        dg.cnpj(10**8 + 1, seed=1, unique=True)


# ------------------------------------------------------------------ PIS, título, CNH, RG
def test_pis_valid_million():
    s = dg.pis(N, seed=1)
    d = digits(s, 11)
    r = 11 - (d[:, :10] * np.array([3, 2, 9, 8, 7, 6, 5, 4, 3, 2])).sum(axis=1) % 11
    assert (np.where(r >= 10, 0, r) == d[:, 10]).all()
    check_sample(val.pis, s)
    fmt = dg.pis(10_000, seed=1, formatted=True)
    assert all(re.fullmatch(r"\d{3}\.\d{5}\.\d{2}-\d", x) for x in fmt.to_list())
    assert strip(fmt) == s.head(10_000).to_list()


def test_voter_id_valid_million():
    s = dg.voter_id(N, seed=1)
    d = digits(s, 12)
    uf = d[:, 8] * 10 + d[:, 9]
    assert ((uf >= 1) & (uf <= 28)).all()
    assert len(np.unique(uf)) == 28
    r1 = (d[:, :8] * np.arange(2, 10)).sum(axis=1) % 11
    r2 = (d[:, 8] * 7 + d[:, 9] * 8 + d[:, 10] * 9) % 11
    assert (np.where(r1 == 10, 0, r1) == d[:, 10]).all()
    assert (np.where(r2 == 10, 0, r2) == d[:, 11]).all()
    # SP e MG: nenhuma linha ambígua (resto 0), válida nas duas leituras da regra
    sp_mg = uf <= 2
    assert not (sp_mg & ((r1 == 0) | (r2 == 0))).any()
    check_sample(val.voter_id, s)
    fmt = dg.voter_id(10_000, seed=1, formatted=True)
    assert all(re.fullmatch(r"\d{4} \d{4} \d{4}", x) for x in fmt.to_list())
    assert strip(fmt) == s.head(10_000).to_list()


def test_cnh_valid_million():
    s = dg.cnh(N, seed=1)
    d = digits(s, 11)
    v1 = (d[:, :9] * np.arange(9, 0, -1)).sum(axis=1) % 11
    dsc = np.where(v1 >= 10, 2, 0)
    d1 = np.where(v1 >= 10, 0, v1)
    d2 = ((d[:, :9] * np.arange(1, 10)).sum(axis=1) % 11 - dsc) % 11
    d2 = np.where(d2 >= 10, 0, d2)
    assert (d1 == d[:, 9]).all()
    assert (d2 == d[:, 10]).all()
    check_sample(val.cnh, s)


def test_rg_valid_million():
    s = dg.rg(N, seed=1)
    m = chars(s, 9)
    d = m[:, :8] - 48
    assert ((d >= 0) & (d <= 9)).all()
    dv = 11 - (d * np.arange(2, 10)).sum(axis=1) % 11
    expected = np.where(dv == 10, ord("X"), np.where(dv == 11, ord("0"), dv + 48))
    assert (expected == m[:, 8]).all()
    assert (m[:, 8] == ord("X")).any()
    check_sample(val.rg, s)
    fmt = dg.rg(10_000, seed=1, formatted=True)
    assert all(re.fullmatch(r"\d{2}\.\d{3}\.\d{3}-[\dX]", x) for x in fmt.to_list())
    assert strip(fmt) == s.head(10_000).to_list()


# ------------------------------------------------------------------ placa, cartão, IBAN, EAN
def test_license_plates():
    mercosul = chars(dg.license_plate(N, seed=1), 7)
    letters = lambda a: (a >= 65) & (a <= 90)  # noqa: E731
    nums = lambda a: (a >= 48) & (a <= 57)  # noqa: E731
    assert letters(mercosul[:, [0, 1, 2, 4]]).all()
    assert nums(mercosul[:, [3, 5, 6]]).all()
    old = chars(dg.license_plate(N, seed=1, style="old"), 8)
    assert letters(old[:, :3]).all()
    assert (old[:, 3] == ord("-")).all()
    assert nums(old[:, 4:]).all()
    assert len(np.unique(mercosul[:, 0])) == 26


def test_credit_cards_luhn_million():
    s = dg.credit_card(N, seed=1)
    raw = s.to_list()
    by_len: dict[int, list[str]] = {}
    for x in raw:
        by_len.setdefault(len(x), []).append(x)
    assert set(by_len) == {15, 16}
    for length, rows in by_len.items():
        m = np.frombuffer("".join(rows).encode(), np.uint8).reshape(-1, length).astype(np.int64) - 48
        t = m[:, ::-1].copy()
        t[:, 1::2] = np.where(t[:, 1::2] > 4, t[:, 1::2] * 2 - 9, t[:, 1::2] * 2)
        assert (t.sum(axis=1) % 10 == 0).all()
    first = Counter(x[0] for x in raw)
    assert 0.52 < first["4"] / N < 0.58
    assert 0.35 < first["5"] / N < 0.41
    assert 0.05 < first["3"] / N < 0.09
    check_sample(val.credit_card, s)
    for brand, rx in [("visa", r"4\d{15}"), ("mastercard", r"5[1-5]\d{14}"), ("amex", r"3[47]\d{13}")]:
        assert all(re.fullmatch(rx, x) for x in dg.credit_card(5_000, seed=2, brand=brand).to_list())
    fmt = dg.credit_card(10_000, seed=1, formatted=True).to_list()
    assert all(re.fullmatch(r"\d{4} \d{4} \d{4} \d{4}|\d{4} \d{6} \d{5}", x) for x in fmt)
    assert [x.replace(" ", "") for x in fmt] == raw[:10_000]


def test_iban_million():
    s = dg.iban(N, seed=1)
    m = chars(s, 29)
    assert (m[:, :2] == np.frombuffer(b"BR", np.uint8)).all()
    assert np.isin(m[:, 27], [ord("C"), ord("P")]).all()
    # módulo 97 do número formado por (resto do IBAN + "BR" + DV), letras como 10..35, em pedaços
    rearranged = np.column_stack([m[:, 4:], m[:, :4]])
    rem = np.zeros(len(m), np.int64)
    for col in rearranged.T:
        is_letter = col >= 65
        v = np.where(is_letter, col - 55, col - 48)
        rem = np.where(is_letter, (rem * 100 + v) % 97, (rem * 10 + v) % 97)
    assert (rem == 1).all()
    check_sample(val.iban, s)


def test_ean13_million():
    s = dg.ean13(N, seed=1)
    d = digits(s, 13)
    assert (d[:, :3] == [7, 8, 9]).all()
    total = (d[:, :12] * np.tile([1, 3], 6)).sum(axis=1)
    assert ((10 - total % 10) % 10 == d[:, 12]).all()
    check_sample(val.ean13, s)


# ------------------------------------------------------------------ rede
def test_uuid_v4_million():
    s = dg.uuid(N, seed=1)
    m = chars(s, 36)
    assert (m[:, [8, 13, 18, 23]] == ord("-")).all()
    assert (m[:, 14] == ord("4")).all()
    assert np.isin(m[:, 19], [ord(c) for c in "89ab"]).all()
    hexpos = np.delete(m, [8, 13, 18, 23], axis=1)
    assert (((hexpos >= 48) & (hexpos <= 57)) | ((hexpos >= 97) & (hexpos <= 102))).all()
    assert s.n_unique() == N


def test_ipv4_public_and_private():
    pub = dg.ipv4(200_000, seed=1).to_list()
    assert all(ipaddress.IPv4Address(x).is_global for x in pub)
    assert len({x.split(".")[0] for x in pub}) > 200
    nets = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
    priv = [ipaddress.IPv4Address(x) for x in dg.ipv4(200_000, seed=1, private=True).to_list()]
    counts = [sum(a in n for a in priv) for n in nets]
    assert sum(counts) == len(priv)
    assert all(0.31 < c / len(priv) < 0.36 for c in counts)


def test_ipv6_and_mac():
    v6 = dg.ipv6(200_000, seed=1).to_list()
    assert all(re.fullmatch(r"[0-9a-f]{4}(:[0-9a-f]{4}){7}", x) for x in v6)
    assert all(ipaddress.IPv6Address(x) for x in v6[:1000])
    mac = dg.mac(200_000, seed=1).to_list()
    assert all(re.fullmatch(r"[0-9a-f]{2}(:[0-9a-f]{2}){5}", x) for x in mac)
    assert all(int(x[:2], 16) % 2 == 0 for x in mac), "MAC unicast: bit 0 do primeiro byte é 0"


def test_url():
    urls = dg.url(200_000, seed=1).to_list()
    tlds = set(dg.DataGen().locale.top_level_domains().names)
    rx = re.compile(r"https://(www\.)?[a-z]+(-[a-z]+)?\.[a-z.]+(/[a-z]+){0,3}/?(\?pagina=\d{1,2})?")
    assert all(rx.fullmatch(x) for x in urls)
    hosts = [urlsplit(x).hostname or "" for x in urls]
    assert all(any(h.endswith("." + t) for t in tlds) for h in hosts[:20_000])
    www = sum(h.startswith("www.") for h in hosts) / len(hosts)
    assert 0.55 < www < 0.65
