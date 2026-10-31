"""Contato: telefone (DDD por população da UF), e-mail e nome de usuário."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .._native import lib, ptr
from ..config.contact import EmailConfig, PhoneConfig, UsernameConfig
from ..core.tables import alias_table
from ..locales import Locale
from ..registry import registry
from .base import Job, Provider, Run, TextJob, probability_threshold

__all__ = ["ascii_word", "pack_words", "weighted_expand"]

# ------------------------------------------------------------------ telefone


@registry.register
class PhoneProvider(Provider[PhoneConfig]):
    kind = "phone"
    config_cls = PhoneConfig
    ns_per_row = 6.0

    def plan(self, run: Run, config: PhoneConfig, inputs: Mapping[str, Any]) -> Job:
        codes, tab = _ddd_tables(run.locale, config.uf)
        style = {"digits": 0, "masked": 1, "intl": 2}[config.style]
        thr = probability_threshold(config.mobile)
        fn, k = lib().dg_phone_views, len(codes)
        # "11987654321" cabe na view; com máscara ou +55 passa de 12 caracteres e vai para o buffer (16 por linha)
        return TextJob(
            run.n,
            16 if style else 0,
            lambda st, m, v, d, _: fn(st, k, ptr(tab), ptr(codes), thr, style, m, v, d, None),
            len(run.blocks),
        )


def _ddd_tables(locale: Locale, uf: str | None) -> tuple[np.ndarray, np.ndarray]:
    """(DDDs como 2 caracteres ASCII em uint16, tabela alias): peso = população da UF / número de DDDs dela."""

    def build() -> tuple[np.ndarray, np.ndarray]:
        states = locale.states()
        if uf is not None and uf not in states:
            raise ValueError(f"UF desconhecida: {uf!r}; use uma de {', '.join(sorted(states))}")
        pairs = [
            (ddd, st.population / len(st.area_codes))
            for code, st in states.items()
            if uf is None or code == uf
            for ddd in st.area_codes
        ]
        chars = np.array([ord(str(d)[0]) | (ord(str(d)[1]) << 8) for d, _ in pairs], np.uint16)
        return chars, alias_table([w for _, w in pairs])

    return locale.cached(("ddd", uf), build)


# ------------------------------------------------------------------ nome de usuário e e-mail
# (troca: sobrenome antes; só_inicial; separador; dígitos 0/2/4) e peso padrão; a = nome, b = sobrenome
USER_STYLES: tuple[tuple[tuple[int, int, str, int], float], ...] = (
    ((0, 0, ".", 0), 28),  # maria.silva
    ((0, 0, "_", 0), 7),  # maria_silva
    ((0, 0, "", 0), 12),  # mariasilva
    ((0, 0, ".", 2), 12),  # maria.silva23
    ((0, 0, "", 2), 10),  # mariasilva23
    ((0, 1, "", 0), 10),  # msilva
    ((0, 0, "", 4), 9),  # mariasilva1987
    ((1, 0, ".", 0), 12),  # silva.maria
)
NAMES_PER_TABLE = (
    4096  # 4096 x 32 bytes = 128 KB por tabela: cabe no cache L2 (com 32 mil nomes o e-mail ficava 40% mais lento)
)
_MAX_USER = 24 + 1 + 24 + 4  # nome + separador + sobrenome + ano
_MAX_EMAIL = _MAX_USER + 1 + 24


def ascii_word(text: str) -> str:
    """Minúsculas sem acento, só a-z e 0-9, até 24 caracteres (``"Conceição"`` -> ``"conceicao"``)."""
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in t if "a" <= c <= "z" or "0" <= c <= "9")[:24] or "x"


def weighted_expand(names: Sequence[str], weights: np.ndarray, size: int = NAMES_PER_TABLE) -> list[str]:
    """Lista de ~``size`` nomes em que cada um aparece proporcional ao peso (o kernel sorteia uniforme nela). Nomes
    raros demais para ganhar uma entrada ficam de fora."""
    w = np.asarray(weights, np.float64)
    cnt = np.floor(w / w.sum() * size + 0.5).astype(np.int64)
    return [names[i] for i in np.flatnonzero(cnt) for _ in range(int(cnt[i]))]


def pack_words(words: Sequence[str], limit: int = 24) -> tuple[np.ndarray, np.ndarray]:
    """Textos -> (32 bytes por texto, comprimentos uint8); corta em ``limit`` bytes sem partir caractere UTF-8."""
    chars = np.zeros((len(words), 32), np.uint8)
    lens = np.empty(len(words), np.uint8)
    for i, w in enumerate(words):
        b = w.encode("utf-8")
        if len(b) > limit:
            b = b[:limit].decode("utf-8", errors="ignore").encode("utf-8")
        chars[i, : len(b)] = np.frombuffer(b, np.uint8)
        lens[i] = len(b)
    return chars, lens


def _name_tables(locale: Locale) -> dict[str, Any]:
    def build() -> dict[str, Any]:
        first, last = locale.first_names(), locale.last_names()
        fch, fln = pack_words([ascii_word(x) for x in weighted_expand(first.names, first.total)])
        lch, lln = pack_words([ascii_word(x) for x in weighted_expand(last.names, last.weights)])
        return {"fch": fch, "fln": fln, "lch": lch, "lln": lln}

    return locale.cached("login_names", build)


def _style_tables(weights: tuple[float, ...] | None) -> tuple[np.ndarray, np.ndarray]:
    w = np.array([x[1] for x in USER_STYLES] if weights is None else weights, np.float64)
    cum = np.cumsum(w / w.sum())[:7]
    thr = np.minimum(np.round(cum * 2.0**32), 2.0**32 - 1).astype(np.uint32)
    tab = np.array([[a, b, ord(c) if c else 0, d] for (a, b, c, d), _ in USER_STYLES], np.uint8)
    return thr, tab


def _login_job(run: Run, style_weights: tuple[float, ...] | None, domains: tuple[np.ndarray, ...] | None) -> TextJob:
    t = _name_tables(run.locale)
    thr, sty = _style_tables(style_weights)
    fn = lib().dg_email_views
    kf, kl = len(t["fln"]), len(t["lln"])
    names = (kf, ptr(t["fch"]), ptr(t["fln"]), kl, ptr(t["lch"]), ptr(t["lln"]), ptr(thr), ptr(sty))
    if domains is None:
        dom: tuple[Any, ...] = (0, 0, None, None, None)
        stride = _MAX_USER
    else:
        dtab, dch, dln = domains
        dom = (1, len(dln), ptr(dtab), ptr(dch), ptr(dln))
        stride = _MAX_EMAIL
    keep = (thr, sty, domains)  # os arrays precisam viver enquanto o job usa os ponteiros

    def kernel(st: int, m: int, v: int, d: int, _: int) -> None:
        assert keep is not None
        fn(st, *names, *dom, m, v, None, d, None, None)

    # textos em sequência; 32 bytes de folga: o kernel copia 24 bytes por nome/domínio
    return TextJob(run.n, stride, kernel, len(run.blocks), packed=True, slack=32)


@registry.register
class UsernameProvider(Provider[UsernameConfig]):
    kind = "username"
    config_cls = UsernameConfig
    ns_per_row = 12.0

    def plan(self, run: Run, config: UsernameConfig, inputs: Mapping[str, Any]) -> Job:
        return _login_job(run, config.style_weights, None)


@registry.register
class EmailProvider(Provider[EmailConfig]):
    kind = "email"
    config_cls = EmailConfig
    ns_per_row = 15.0

    def plan(self, run: Run, config: EmailConfig, inputs: Mapping[str, Any]) -> Job:
        if config.domains is None:
            d = run.locale.email_domains()
            names, weights = d.names, d.weights
        else:
            names = config.domains
            weights = np.array(config.domain_weights or [1.0] * len(names), np.float64)
        dch, dln = pack_words(list(names))
        return _login_job(run, config.style_weights, (alias_table(weights), dch, dln))
