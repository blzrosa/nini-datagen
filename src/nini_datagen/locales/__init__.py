"""Locales disponíveis. Por enquanto só ``pt_BR``; outros entram um a um."""

from __future__ import annotations

import threading

from .base import FirstNames, Locale, WeightedNames

__all__ = ["FirstNames", "Locale", "WeightedNames", "available", "get_locale"]

_lock = threading.Lock()
_instances: dict[str, Locale] = {}


def _factories() -> dict[str, type[Locale]]:
    from .pt_BR import PtBR  # noqa: PLC0415

    return {"pt_BR": PtBR}


def available() -> list[str]:
    return sorted(_factories())


def get_locale(locale: str | Locale = "pt_BR") -> Locale:
    """O locale pelo código (``"pt_BR"``); um objeto `Locale` passa direto. Cada código é instanciado uma vez."""
    if isinstance(locale, Locale):
        return locale
    factories = _factories()
    if locale not in factories:
        raise ValueError(f"locale {locale!r} não existe; disponíveis: {', '.join(sorted(factories))}")
    with _lock:
        if locale not in _instances:
            _instances[locale] = factories[locale]()
        return _instances[locale]
