"""`DataGen`: o ponto de entrada (Facade). Guarda semente, locale e threads; cada método gera uma coluna.

Reprodutibilidade: a coluna depende só de (seed, nome da coluna, configuração, n). O nome padrão é o tipo do gerador,
então ``g.integer(10)`` duas vezes dá o mesmo resultado; para colunas independentes do mesmo tipo, dê nomes
diferentes (``g.integer(10, name="a")``, ``g.integer(10, name="b")``).
"""

from __future__ import annotations

from typing import Any

import polars as pl

from . import providers as _providers  # noqa: F401 (registra os geradores)
from .core.rng import new_seed
from .locales import Locale, get_locale
from .providers.base import Context
from .registry import registry

__all__ = ["DataGen"]


class DataGen:
    """Gerador de colunas com semente, locale e número de threads fixos.

    >>> g = DataGen(seed=42)
    >>> g.first_name(1_000_000)                # doctest: +SKIP
    >>> g.integer(10, low=1, high=6)           # doctest: +SKIP
    >>> g.choice(5, ["a", "b"], weights=[3, 1])  # doctest: +SKIP

    ``seed=None`` sorteia uma semente (veja `seed`); ``threads=None`` usa todas as CPUs (ou ``NINI_DATAGEN_THREADS``).
    O resultado é o mesmo para qualquer número de threads.
    """

    def __init__(self, seed: int | None = None, *, locale: str | Locale = "pt_BR", threads: int | None = None) -> None:
        self._ctx = Context(new_seed() if seed is None else seed, get_locale(locale), threads)
        # valida a semente agora (e não na primeira coluna)
        from .core.rng import seed_state  # noqa: PLC0415

        seed_state(self._ctx.seed, "check")

    @property
    def seed(self) -> int:
        return self._ctx.seed

    @property
    def locale(self) -> Locale:
        return self._ctx.locale

    @property
    def threads(self) -> int | None:
        return self._ctx.threads

    def __repr__(self) -> str:
        return f"DataGen(seed={self.seed}, locale={self.locale.code!r}, threads={self.threads})"

    def generate(self, kind: str, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Gera ``n`` valores do tipo ``kind`` (``"integer"``, ``"first_name"``...; veja `kinds`).

        ``config``: o objeto de configuração (ex. ``IntegerConfig(low=1)``), um dict, ou nada; ``kwargs`` completam ou
        sobrescrevem campos. Nome de campo errado ou valor inválido dá ``pydantic.ValidationError``.
        """
        provider = registry.get(kind)
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError(f"n deve ser um inteiro >= 0, veio {n!r}")
        inputs = provider.take_inputs(kwargs)
        cfg = registry.config(kind, config, **kwargs)
        return provider.generate(n, cfg, self._ctx, inputs)

    @staticmethod
    def kinds() -> list[str]:
        """Tipos de gerador disponíveis."""
        return registry.kinds()

    # ------------------------------------------------------------------ atalhos (um por tipo)
    def integer(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Inteiros uniformes em [low, high] (`IntegerConfig`)."""
        return self.generate("integer", n, config, **kwargs)

    def uniform(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Reais uniformes em [low, high) (`UniformConfig`)."""
        return self.generate("uniform", n, config, **kwargs)

    def normal(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Normal(mean, std) (`NormalConfig`)."""
        return self.generate("normal", n, config, **kwargs)

    def lognormal(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """exp(Normal(mean, sigma)) (`LognormalConfig`)."""
        return self.generate("lognormal", n, config, **kwargs)

    def boolean(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Booleanos com P(True) = p (`BooleanConfig`)."""
        return self.generate("boolean", n, config, **kwargs)

    def date(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Datas uniformes em [start, end] (`DateConfig`)."""
        return self.generate("date", n, config, **kwargs)

    def datetime(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Instantes uniformes em [start, end) (`DatetimeConfig`)."""
        return self.generate("datetime", n, config, **kwargs)

    def choice(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Sorteio em lista, com ou sem pesos: ``choice(n, ["a", "b"], weights=[3, 1])`` (`ChoiceConfig`)."""
        return self.generate("choice", n, config, **kwargs)

    def sex(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Sexo ("F"/"M" ou ``labels``) com a proporção do locale (`SexConfig`)."""
        return self.generate("sex", n, config, **kwargs)

    def age(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Idades com a pirâmide etária do locale (`AgeConfig`)."""
        return self.generate("age", n, config, **kwargs)

    def first_name(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Primeiros nomes; ``sex="F"``/``"M"`` ou ``sex=<coluna de sexo>`` (`FirstNameConfig`)."""
        return self.generate("first_name", n, config, **kwargs)

    def last_name(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Sobrenomes (`LastNameConfig`)."""
        return self.generate("last_name", n, config, **kwargs)

    def full_name(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Nome + um ou dois sobrenomes; ``sex`` como em `first_name` (`FullNameConfig`)."""
        return self.generate("full_name", n, config, **kwargs)
