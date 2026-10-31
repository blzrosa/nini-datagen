"""Identificadores de rede: UUID v4, IPv4 (público ou privado), IPv6, MAC e URL."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from .._native import lib, ptr
from ..config.network import IPv4Config, IPv6Config, MACConfig, URLConfig, UUIDConfig
from ..core.tables import alias_table
from ..locales import Locale
from ..registry import registry
from .base import Job, Provider, Run, TextJob
from .documents import id_job

__all__ = ["url_tables"]


@registry.register
class UUIDProvider(Provider[UUIDConfig]):
    kind = "uuid"
    config_cls = UUIDConfig
    ns_per_row = 8.0

    def plan(self, run: Run, config: UUIDConfig, inputs: Mapping[str, Any]) -> Job:
        fn = lib().dg_uuid_views
        return TextJob(run.n, 36, lambda st, m, v, d, _: fn(st, m, v, d), len(run.blocks))


@registry.register
class IPv4Provider(Provider[IPv4Config]):
    kind = "ipv4"
    config_cls = IPv4Config
    ns_per_row = 5.0

    def plan(self, run: Run, config: IPv4Config, inputs: Mapping[str, Any]) -> Job:
        fn, priv = lib().dg_ipv4_views, int(config.private)
        # o kernel escreve 16 bytes por linha no buffer; só as que passam de 12 caracteres apontam para lá
        return TextJob(run.n, 16, lambda st, m, v, d, _: fn(st, priv, m, v, d), len(run.blocks))


@registry.register
class IPv6Provider(Provider[IPv6Config]):
    kind = "ipv6"
    config_cls = IPv6Config
    ns_per_row = 12.0

    def plan(self, run: Run, config: IPv6Config, inputs: Mapping[str, Any]) -> Job:
        return id_job(run, 9, 0, 40)


@registry.register
class MACProvider(Provider[MACConfig]):
    kind = "mac"
    config_cls = MACConfig
    ns_per_row = 8.0

    def plan(self, run: Run, config: MACConfig, inputs: Mapping[str, Any]) -> Job:
        return id_job(run, 10, 0, 24)


def _pack(words: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Palavras -> (32 bytes por palavra, comprimentos): o kernel copia 24 bytes de uma vez."""
    chars = np.zeros((len(words), 32), np.uint8)
    lens = np.empty(len(words), np.uint8)
    for i, w in enumerate(words):
        b = w.encode("ascii")
        if not b or len(b) > 24:
            raise ValueError(f"palavra de URL deve ter de 1 a 24 caracteres ASCII: {w!r}")
        chars[i, : len(b)] = np.frombuffer(b, np.uint8)
        lens[i] = len(b)
    return chars, lens


def url_tables(locale: Locale) -> dict[str, Any]:
    def build() -> dict[str, Any]:
        words = locale.url_words()
        tlds = locale.top_level_domains()
        wch, wln = _pack(words)
        tch, tln = _pack(tlds.names)
        return {
            "k": len(words), "wch": wch, "wln": wln,  # palavras: sorteio uniforme no kernel
            "kt": len(tlds.names), "tch": tch, "tln": tln, "ttab": alias_table(tlds.weights),
            # https://www. + 2 palavras + . + tld + 3 trechos + /?pagina=99
            "max_len": 12 + 2 * int(wln.max()) + 1 + 1 + int(tln.max()) + 3 * (1 + int(wln.max())) + 1 + 8 + 2,
        }  # fmt: skip

    return locale.cached("url_tables", build)


@registry.register
class URLProvider(Provider[URLConfig]):
    kind = "url"
    config_cls = URLConfig
    ns_per_row = 25.0

    def plan(self, run: Run, config: URLConfig, inputs: Mapping[str, Any]) -> Job:
        t = url_tables(run.locale)
        fn = lib().dg_url_views
        args = (t["k"], ptr(t["wch"]), ptr(t["wln"]), t["kt"], ptr(t["tch"]), ptr(t["tln"]), ptr(t["ttab"]))
        # textos em sequência (stride = limite por linha); 32 bytes de folga: o kernel copia 24 bytes por palavra
        return TextJob(
            run.n, t["max_len"], lambda st, m, v, d, _: fn(st, *args, m, v, d), len(run.blocks), packed=True, slack=32
        )
