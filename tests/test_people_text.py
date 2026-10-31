"""Telefone, e-mail, nome de usuário, empresa, veículo, profissão e frases por gramática."""

from __future__ import annotations

import itertools
import re
from collections import Counter

import numpy as np
import pytest
from pydantic import ValidationError

import nini_datagen as dg
from nini_datagen.config.text import SentenceConfig
from nini_datagen.core.blocks import BLOCK_ROWS
from nini_datagen.core.grammar import compile_grammar, parse_option
from nini_datagen.locales import get_locale
from nini_datagen.providers import text as text_mod

N = 200_000
LOC = get_locale("pt_BR")


# ------------------------------------------------------------------ telefone
def test_phone_formats_and_mobile_share():
    digits = dg.phone(N, seed=1).to_list()
    assert all(re.fullmatch(r"[1-9][1-9](9\d{8}|[2-5]\d{7})", x) for x in digits)
    mobile = sum(len(x) == 11 for x in digits) / N
    assert abs(mobile - 0.8) < 0.01
    masked = dg.phone(N, seed=1, style="masked").to_list()
    assert all(re.fullmatch(r"\([1-9][1-9]\) (9\d{4}|[2-5]\d{3})-\d{4}", x) for x in masked)
    assert [re.sub(r"\D", "", x) for x in masked] == digits  # mesmo número, só a máscara muda
    intl = dg.phone(1000, seed=1, style="intl").to_list()
    assert [x[3:] for x in intl] == digits[:1000]
    assert all(x.startswith("+55") for x in intl)
    assert all(len(x) == 11 for x in dg.phone(1000, seed=1, mobile=1.0).to_list())
    assert all(len(x) == 10 for x in dg.phone(1000, seed=1, mobile=0.0).to_list())


def test_phone_ddd_follows_population():
    ddd = Counter(x[:2] for x in dg.phone(N, seed=2).to_list())
    states = LOC.states()
    total = sum(st.population for st in states.values())
    sp = sum(ddd[str(d)] for d in states["SP"].area_codes) / N
    assert abs(sp - states["SP"].population / total) < 0.005
    assert set(ddd) == {str(d) for st in states.values() for d in st.area_codes}  # os 67 DDDs aparecem
    only_rj = {x[:2] for x in dg.phone(5000, seed=2, uf="rj").to_list()}
    assert only_rj == {"21", "22", "24"}
    with pytest.raises(ValueError, match="UF desconhecida"):
        dg.phone(10, seed=1, uf="XX")


# ------------------------------------------------------------------ e-mail e nome de usuário
USER = r"[a-z0-9]+([._]?[a-z0-9]+)?"


def test_username_styles():
    users = dg.username(N, seed=1).to_list()
    assert all(re.fullmatch(USER, u) for u in users)
    dotted = sum("." in u and not u[-1].isdigit() for u in users) / N  # maria.silva + silva.maria
    assert 0.37 < dotted < 0.43
    year = sum(bool(re.search(r"(19[5-9]\d|200\d)$", u)) for u in users) / N
    assert 0.07 < year < 0.11
    only_dot = dg.username(1000, seed=1, style_weights=[1, 0, 0, 0, 0, 0, 0, 0]).to_list()
    assert all(re.fullmatch(r"[a-z0-9]+\.[a-z0-9]+", u) for u in only_dot)


def test_email_domains():
    emails = dg.email(N, seed=1).to_list()
    assert all(re.fullmatch(USER + r"@[a-z0-9.]+", e) for e in emails)
    dom = Counter(e.split("@")[1] for e in emails)
    assert abs(dom["gmail.com"] / N - 0.55) < 0.01
    custom = dg.email(5000, seed=1, domains=["Empresa.com.br", "x.org"], domain_weights=[3, 1]).to_list()
    c = Counter(e.split("@")[1] for e in custom)
    assert set(c) == {"empresa.com.br", "x.org"}
    assert 0.72 < c["empresa.com.br"] / 5000 < 0.78
    with pytest.raises(ValidationError, match="domain_weights"):
        dg.EmailConfig.model_validate({"domain_weights": [1.0]})
    with pytest.raises(ValidationError, match="um por domínio"):
        dg.EmailConfig.model_validate({"domains": ["a.com"], "domain_weights": [1.0, 2.0]})
    with pytest.raises(ValidationError, match="domínio inválido"):
        dg.EmailConfig.model_validate({"domains": ["a b.com"]})
    with pytest.raises(ValidationError):
        dg.UsernameConfig.model_validate({"style_weights": [1, 2]})


# ------------------------------------------------------------------ empresa, veículo, profissão
def test_company_patterns():
    names = dg.company(N, seed=1).to_list()
    sectors, _, types = LOC.company_parts()
    assert all(any(n.endswith(" " + t) for t in types.names) for n in names[:20_000])
    assert all(any(f" {s} " in n for s in sectors) for n in names[:20_000])
    partners = sum(" & " in n for n in names) / N
    assert 0.18 < partners < 0.22
    ltda = sum(n.endswith(" LTDA") for n in names) / N
    assert abs(ltda - 0.55) < 0.01
    assert any("ç" in n or "ã" in n for n in names)  # acentos preservados (UTF-8)


def test_vehicle_struct():
    s = dg.vehicle(N, seed=1)
    df = s.struct.unnest()
    assert df.columns == ["brand", "model", "year"]
    v = LOC.vehicles()
    models = {b: set(m.names) for b, m in zip(v.brands.names, v.models, strict=True)}
    rows = list(zip(df["brand"].to_list(), df["model"].to_list(), df["year"].to_list(), strict=True))
    assert all(m in models[b] for b, m, _ in rows)
    years = Counter(y for _, _, y in rows)
    assert min(years) == 2005
    assert max(years) == 2025
    assert years[2025] > 3 * years[2005]
    fiat = sum(b == "Fiat" for b, _, _ in rows) / N
    assert abs(fiat - 0.20 / sum(v.brands.weights)) < 0.01
    narrow = dg.vehicle(1000, seed=1, year_low=2020, year_high=2020).struct.unnest()["year"].to_list()
    assert set(narrow) == {2020}
    with pytest.raises(ValidationError, match="year_high"):
        dg.VehicleConfig(year_low=2020, year_high=2019)


def test_occupation_zipf():
    occ = Counter(dg.occupation(N, seed=1).to_list())
    names = LOC.occupations()
    assert set(occ) == set(names)
    assert occ[names[0]] > occ[names[10]] > occ[names[-1]]
    flat = Counter(dg.occupation(N, seed=1, zipf=0).to_list())
    assert max(flat.values()) / min(flat.values()) < 1.3


# ------------------------------------------------------------------ gramática
def test_parse_option():
    assert parse_option("O {pessoa} pediu {{x}}") == ["O ", ("ref", "pessoa"), " pediu {x}"]
    assert parse_option("{a}{b}") == [("ref", "a"), ("ref", "b")]
    assert parse_option("") == []


def test_compile_grammar_leaves_and_lengths():
    g = compile_grammar({"frase": ["Pedido {d}{d} {x}.", ("ok", 0)], "d": list("0123456789"), "x": ["{d}", "ab"]})
    kinds = Counter(t >> 30 for t in g.tok.tolist())  # 0 literal, 1 folha, 2 referência, 3 fim da opção
    assert kinds[3] == len(g.opt_off) - 1  # toda opção termina com o token de fim
    assert "<d+d>" in g.names  # {d}{d} vizinhas viram uma folha de 100 opções
    assert kinds[1] == 2  # <d+d> em "Pedido..." e {d} em x
    assert kinds[2] == 1  # {x} tem slot: referência comum
    assert g.max_len == len("Pedido 00 ab.")
    assert g.mean_len == pytest.approx(len("Pedido 00 ") + 1.5 + 1)  # a opção de peso 0 não conta
    for bad, match in [
        ({"frase": ["{y}"]}, "não está definido"),
        ({"frase": ["{a}"], "a": ["{frase}"]}, "ciclo"),
        ({"frase": []}, "lista não vazia"),
        ({"frase": [("a", -1)]}, "peso inválido"),
        ({"frase": [("a", 0)]}, "zerados"),
        ({"x": ["a"]}, "raiz"),
    ]:
        with pytest.raises(ValueError, match=match):
            compile_grammar(bad)
    with pytest.raises(ValueError, match="row_root"):
        compile_grammar({"frase": ["texto {a}"], "a": ["x"]}, row_root=True)


def sentences_of(text: str) -> int:
    return len(re.findall(r"[.!?](?= [A-ZÁÉÍÓÚÂÊÔÃÕÇ]|$)", text))


def test_sentence_shape():
    for theme in ["geral", *LOC.grammar()[1]]:
        rows = dg.sentence(20_000, seed=1, theme=theme).to_list()
        assert all(r[0].isupper() for r in rows), theme
        assert all(r.endswith((".", "!", "?")) for r in rows), theme
        assert all("{" not in r and "}" not in r for r in rows), theme
        assert len(set(rows)) > 1000, theme  # o tema cadastro é o menos variado (~1.500 frases)
    with pytest.raises(ValueError, match="tema desconhecido"):
        dg.sentence(10, seed=1, theme="nenhum")


def test_paragraph_sentence_count_and_theme_per_row():
    rows = dg.paragraph(20_000, seed=1, sentences=(2, 3)).to_list()
    counts = Counter(sentences_of(r) for r in rows)
    assert set(counts) <= {2, 3, 4}  # 4: alguma frase do tema pode ter "!" ou "?" no meio
    assert counts[2] > 0.3 * len(rows)
    assert counts[3] > 0.3 * len(rows)
    with pytest.raises(ValidationError, match="sentences"):
        dg.ParagraphConfig(sentences=(3, 2))


def pairs(row: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?<=[.!?]) (?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", row)
    return list(itertools.pairwise(parts))


def test_paragraph_does_not_repeat_the_previous_sentence():
    # com 2 frases possíveis, cada novo sorteio ainda repete com chance 1/2: 16 tentativas deixam 1 em 65.536
    rows = dg.paragraph(5000, seed=1, templates=["Um.", "Dois."], sentences=(6, 6)).to_list()
    repeated = sum(a == b for r in rows for a, b in pairs(r))
    assert repeated <= 3
    # gramática com uma frase só: depois das tentativas aceita a repetição (não trava)
    assert dg.paragraph(3, seed=1, templates=["Igual."], sentences=(3, 3)).to_list() == ["Igual. Igual. Igual."] * 3
    for row in dg.paragraph(20_000, seed=2, theme="avaliacao").to_list():
        assert all(a != b for a, b in pairs(row)), row


def test_leaf_merge_keeps_the_distribution():
    rows = dg.sentence(N, seed=3, templates=["{d1}{d}{d}{d}"]).to_list()
    first = Counter(r[0] for r in rows)
    assert set(first) == set("123456789")
    last = Counter(r[-1] for r in rows)
    assert max(last.values()) / min(last.values()) < 1.1
    assert len(set(rows)) > 8000  # 9.000 possibilidades


def test_custom_templates_and_slots():
    rows = dg.sentence(
        5000, seed=1, templates=["pedido {cod} enviado {prazo}.", ("Sem observações.", 3)], slots={"cod": ["{d}{d}{d}"]}
    ).to_list()
    c = Counter(r == "Sem observações." for r in rows)
    assert 0.72 < c[True] / 5000 < 0.78
    assert all(re.fullmatch(r"Pedido \d{3} enviado .+\.", r) for r in rows if r != "Sem observações.")
    with pytest.raises(ValidationError, match="templates"):
        dg.SentenceConfig.model_validate({"slots": {"x": ["a"]}})
    cfg = dg.SentenceConfig.model_validate({"templates": ["a {x}"], "slots": {"x": ["b"]}})
    assert hash(cfg) == hash(dg.SentenceConfig(templates=("a {x}",), slots=(("x", ("b",)),)))
    with pytest.raises(ValueError, match="não está definido"):
        dg.sentence(3, seed=1, templates=["{nada}"])


def test_grammar_buffer_split_does_not_change_output(monkeypatch):
    """Com o buffer cortado em vários pedaços por bloco, o texto é o mesmo (o kernel continua do mesmo estado)."""
    ref = dg.paragraph(BLOCK_ROWS + 300, seed=5).to_list()
    original = text_mod.GrammarJob.__init__

    def tiny(self, *a, **k):
        original(self, *a, **k)
        self.mean_row = 1.0  # força buffers pequenos: ~4 KB cada, várias linhas por buffer

    monkeypatch.setattr(text_mod.GrammarJob, "__init__", tiny)
    job_parts = []
    fill = text_mod.GrammarJob.fill

    def spy(self, block, state):
        fill(self, block, state)
        job_parts.append(len(self.parts[block.index]))

    monkeypatch.setattr(text_mod.GrammarJob, "fill", spy)
    assert dg.paragraph(BLOCK_ROWS + 300, seed=5).to_list() == ref
    assert max(job_parts) > 100


def test_grammar_is_cached_per_config():
    a = text_mod.grammar_for(LOC, SentenceConfig(theme="saude"))
    assert text_mod.grammar_for(LOC, SentenceConfig(theme="saude")) is a
    assert np.all(a.leaf_lit[a.leaf_lit != 0] >> np.uint64(32) <= a.max_len)
