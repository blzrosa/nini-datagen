"""`DataGen`: o ponto de entrada (Facade). Guarda semente, locale e threads; cada método gera uma coluna.

Reprodutibilidade: a coluna depende só de (seed, nome da coluna, configuração, n). O nome padrão é o tipo do gerador,
então ``g.integer(10)`` duas vezes dá o mesmo resultado; para colunas independentes do mesmo tipo, dê nomes
diferentes (``g.integer(10, name="a")``, ``g.integer(10, name="b")``).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import polars as pl

from . import providers as _providers  # noqa: F401 (registra os geradores)
from .core.rng import new_seed
from .locales import Locale, get_locale
from .providers.base import Context
from .registry import registry
from .schema import Schema, as_schema
from .schema import scan as _scan

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
        _check_n(n)
        inputs = provider.take_inputs(kwargs)
        cfg = registry.config(kind, config, **kwargs)
        return provider.generate(n, cfg, self._ctx, inputs)

    def table(self, n: int, schema: Schema | Mapping[str, Any]) -> pl.DataFrame:
        """Tabela de ``n`` linhas a partir de um `Schema` (ou do dict que o descreve).

        Cada coluna sai igual a ``generate(tipo, n, name=coluna, ...)``: reordenar, tirar ou acrescentar colunas não
        muda as outras. As colunas são preenchidas bloco a bloco, todas de uma vez, com os blocos em paralelo.
        """
        _check_n(n)
        return as_schema(schema).bind(self.locale).run(self._ctx, n)

    def scan(self, n: int, schema: Schema | Mapping[str, Any], *, batch_size: int | None = None) -> pl.LazyFrame:
        """A mesma tabela de `table` como ``pl.LazyFrame``: gera em lotes só as colunas e as linhas pedidas.

        ``g.scan(10**9, schema).select("cpf").head(5).collect()`` gera 5 CPFs. ``batch_size``: linhas por lote
        (arredondado para múltiplo de 65.536; padrão 1.048.576). Expressões do schema devem ser linha a linha.
        """
        _check_n(n)
        return _scan(as_schema(schema).bind(self.locale), self._ctx, n, batch_size=batch_size)

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

    def cpf(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """CPF válido; ``formatted``, ``unique`` (sem repetição) (`CPFConfig`)."""
        return self.generate("cpf", n, config, **kwargs)

    def cnpj(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """CNPJ válido, numérico ou ``alphanumeric``; ``branch``, ``formatted``, ``unique`` (`CNPJConfig`)."""
        return self.generate("cnpj", n, config, **kwargs)

    def pis(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """PIS/PASEP/NIS válido (`PISConfig`)."""
        return self.generate("pis", n, config, **kwargs)

    def voter_id(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Título de eleitor válido (`VoterIDConfig`)."""
        return self.generate("voter_id", n, config, **kwargs)

    def cnh(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Número de registro da CNH válido (`CNHConfig`)."""
        return self.generate("cnh", n, config, **kwargs)

    def rg(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """RG no padrão de SP, com DV (`RGConfig`)."""
        return self.generate("rg", n, config, **kwargs)

    def license_plate(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Placa de veículo, Mercosul ou antiga (`LicensePlateConfig`)."""
        return self.generate("license_plate", n, config, **kwargs)

    def credit_card(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Número de cartão com dígito de Luhn correto (`CreditCardConfig`)."""
        return self.generate("credit_card", n, config, **kwargs)

    def iban(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """IBAN do Brasil válido (`IBANConfig`)."""
        return self.generate("iban", n, config, **kwargs)

    def ean13(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Código de barras EAN-13 brasileiro (`EAN13Config`)."""
        return self.generate("ean13", n, config, **kwargs)

    def uuid(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """UUID versão 4 (`UUIDConfig`)."""
        return self.generate("uuid", n, config, **kwargs)

    def ipv4(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Endereço IPv4 público ou ``private`` (`IPv4Config`)."""
        return self.generate("ipv4", n, config, **kwargs)

    def ipv6(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Endereço IPv6 completo (`IPv6Config`)."""
        return self.generate("ipv6", n, config, **kwargs)

    def mac(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Endereço MAC unicast (`MACConfig`)."""
        return self.generate("mac", n, config, **kwargs)

    def url(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """URL plausível (`URLConfig`)."""
        return self.generate("url", n, config, **kwargs)

    def phone(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Telefone com DDD pela população da UF; ``style``, ``mobile``, ``uf`` (`PhoneConfig`)."""
        return self.generate("phone", n, config, **kwargs)

    def email(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """E-mail a partir de nome e sobrenome sem acento; ``domains`` (`EmailConfig`)."""
        return self.generate("email", n, config, **kwargs)

    def username(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Nome de usuário em 8 estilos (`UsernameConfig`)."""
        return self.generate("username", n, config, **kwargs)

    def company(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Razão social plausível (`CompanyConfig`)."""
        return self.generate("company", n, config, **kwargs)

    def vehicle(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Struct ``{brand, model, year}`` coerente; ``.struct.unnest()`` separa (`VehicleConfig`)."""
        return self.generate("vehicle", n, config, **kwargs)

    def occupation(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Profissão (`OccupationConfig`)."""
        return self.generate("occupation", n, config, **kwargs)

    def sentence(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Uma frase por gramática; ``theme``, ``templates``, ``slots`` (`SentenceConfig`)."""
        return self.generate("sentence", n, config, **kwargs)

    def paragraph(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Parágrafo de ``sentences=(mín, máx)`` frases (`ParagraphConfig`)."""
        return self.generate("paragraph", n, config, **kwargs)

    def cep(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """CEP real do CNEFE, pelo número de endereços; ``formatted``, ``uf``, ``source`` (`CepConfig`)."""
        return self.generate("cep", n, config, **kwargs)

    def address(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Endereço real do CNEFE como struct; ``.struct.unnest()`` separa as colunas (`AddressConfig`)."""
        return self.generate("address", n, config, **kwargs)

    def city(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Município pela população; ``uf``, ``with_state`` (`CityConfig`)."""
        return self.generate("city", n, config, **kwargs)

    def state(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """UF pela população (`StateConfig`)."""
        return self.generate("state", n, config, **kwargs)

    def birthdate(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Data de nascimento coerente com ``age=<coluna de idades>`` na data ``on`` (`BirthdateConfig`)."""
        return self.generate("birthdate", n, config, **kwargs)

    def correlated(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Real com correlação ``rho`` com ``other=<coluna numérica>`` (`CorrelatedConfig`)."""
        return self.generate("correlated", n, config, **kwargs)

    def choice_by(self, n: int, config: Any = None, /, **kwargs: Any) -> pl.Series:
        """Escolha que depende de ``by=<coluna>``: ``options={valor: lista}`` (`ChoiceByConfig`)."""
        return self.generate("choice_by", n, config, **kwargs)


def _check_n(n: Any) -> None:
    if isinstance(n, bool) or not isinstance(n, int) or n < 0:
        raise ValueError(f"n deve ser um inteiro >= 0, veio {n!r}")
