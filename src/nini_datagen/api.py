"""Funções soltas: ``nini_datagen.integer(n, ...)`` é um atalho para ``DataGen(seed, ...).integer(n, ...)``.

Sem ``seed``, cada chamada sorteia uma semente nova (valores diferentes a cada vez). Com ``seed``, o resultado é sempre
o mesmo.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import polars as pl

from .generator import DataGen
from .locales import Locale
from .schema import Schema

__all__ = [
    "address",
    "age",
    "birthdate",
    "boolean",
    "cep",
    "choice",
    "choice_by",
    "city",
    "cnh",
    "cnpj",
    "company",
    "correlated",
    "cpf",
    "credit_card",
    "date",
    "datetime",
    "ean13",
    "email",
    "first_name",
    "full_name",
    "generate",
    "iban",
    "integer",
    "ipv4",
    "ipv6",
    "last_name",
    "license_plate",
    "lognormal",
    "mac",
    "normal",
    "occupation",
    "paragraph",
    "phone",
    "pis",
    "rg",
    "scan",
    "sentence",
    "sex",
    "state",
    "table",
    "uniform",
    "url",
    "username",
    "uuid",
    "vehicle",
    "voter_id",
    "write_parquet_dataset",
]


def generate(
    kind: str,
    n: int,
    config: Any = None,
    /,
    *,
    seed: int | None = None,
    locale: str | Locale = "pt_BR",
    threads: int | None = None,
    **kwargs: Any,
) -> pl.Series:
    """Gera ``n`` valores do tipo ``kind``; veja `DataGen.generate`."""
    return DataGen(seed, locale=locale, threads=threads).generate(kind, n, config, **kwargs)


def table(
    n: int,
    schema: Schema | Mapping[str, Any],
    *,
    seed: int | None = None,
    locale: str | Locale = "pt_BR",
    threads: int | None = None,
) -> pl.DataFrame:
    """Tabela de ``n`` linhas; veja `DataGen.table`."""
    return DataGen(seed, locale=locale, threads=threads).table(n, schema)


def scan(
    n: int,
    schema: Schema | Mapping[str, Any],
    *,
    seed: int | None = None,
    locale: str | Locale = "pt_BR",
    threads: int | None = None,
    batch_size: int | None = None,
) -> pl.LazyFrame:
    """Tabela como ``pl.LazyFrame``, gerada sob demanda; veja `DataGen.scan`.

    Sem ``seed``, a semente é sorteada uma vez aqui: coletar o mesmo LazyFrame duas vezes dá a mesma tabela.
    """
    return DataGen(seed, locale=locale, threads=threads).scan(n, schema, batch_size=batch_size)


def write_parquet_dataset(
    path: str | Path,
    n: int,
    schema: Schema | Mapping[str, Any],
    *,
    seed: int | None = None,
    locale: str | Locale = "pt_BR",
    threads: int | None = None,
    **options: Any,
) -> list[Path]:
    """Grava ``n`` linhas em Parquet, em lotes; veja `DataGen.write_parquet_dataset` (as opções são as mesmas)."""
    return DataGen(seed, locale=locale, threads=threads).write_parquet_dataset(path, n, schema, **options)


def _shortcut(kind: str, doc: str) -> Any:
    def fn(
        n: int,
        config: Any = None,
        /,
        *,
        seed: int | None = None,
        locale: str | Locale = "pt_BR",
        threads: int | None = None,
        **kwargs: Any,
    ) -> pl.Series:
        return generate(kind, n, config, seed=seed, locale=locale, threads=threads, **kwargs)

    fn.__name__ = fn.__qualname__ = kind
    fn.__doc__ = doc + "\n\n``seed``, ``locale`` e ``threads`` como em `DataGen`; o resto vai para a configuração."
    return fn


integer = _shortcut("integer", DataGen.integer.__doc__ or "")
uniform = _shortcut("uniform", DataGen.uniform.__doc__ or "")
normal = _shortcut("normal", DataGen.normal.__doc__ or "")
lognormal = _shortcut("lognormal", DataGen.lognormal.__doc__ or "")
boolean = _shortcut("boolean", DataGen.boolean.__doc__ or "")
date = _shortcut("date", DataGen.date.__doc__ or "")
datetime = _shortcut("datetime", DataGen.datetime.__doc__ or "")
choice = _shortcut("choice", DataGen.choice.__doc__ or "")
sex = _shortcut("sex", DataGen.sex.__doc__ or "")
age = _shortcut("age", DataGen.age.__doc__ or "")
first_name = _shortcut("first_name", DataGen.first_name.__doc__ or "")
last_name = _shortcut("last_name", DataGen.last_name.__doc__ or "")
full_name = _shortcut("full_name", DataGen.full_name.__doc__ or "")
cpf = _shortcut("cpf", DataGen.cpf.__doc__ or "")
cnpj = _shortcut("cnpj", DataGen.cnpj.__doc__ or "")
pis = _shortcut("pis", DataGen.pis.__doc__ or "")
voter_id = _shortcut("voter_id", DataGen.voter_id.__doc__ or "")
cnh = _shortcut("cnh", DataGen.cnh.__doc__ or "")
rg = _shortcut("rg", DataGen.rg.__doc__ or "")
license_plate = _shortcut("license_plate", DataGen.license_plate.__doc__ or "")
credit_card = _shortcut("credit_card", DataGen.credit_card.__doc__ or "")
iban = _shortcut("iban", DataGen.iban.__doc__ or "")
ean13 = _shortcut("ean13", DataGen.ean13.__doc__ or "")
uuid = _shortcut("uuid", DataGen.uuid.__doc__ or "")
ipv4 = _shortcut("ipv4", DataGen.ipv4.__doc__ or "")
ipv6 = _shortcut("ipv6", DataGen.ipv6.__doc__ or "")
mac = _shortcut("mac", DataGen.mac.__doc__ or "")
url = _shortcut("url", DataGen.url.__doc__ or "")
phone = _shortcut("phone", DataGen.phone.__doc__ or "")
email = _shortcut("email", DataGen.email.__doc__ or "")
username = _shortcut("username", DataGen.username.__doc__ or "")
company = _shortcut("company", DataGen.company.__doc__ or "")
vehicle = _shortcut("vehicle", DataGen.vehicle.__doc__ or "")
occupation = _shortcut("occupation", DataGen.occupation.__doc__ or "")
sentence = _shortcut("sentence", DataGen.sentence.__doc__ or "")
paragraph = _shortcut("paragraph", DataGen.paragraph.__doc__ or "")
cep = _shortcut("cep", DataGen.cep.__doc__ or "")
address = _shortcut("address", DataGen.address.__doc__ or "")
city = _shortcut("city", DataGen.city.__doc__ or "")
state = _shortcut("state", DataGen.state.__doc__ or "")
birthdate = _shortcut("birthdate", DataGen.birthdate.__doc__ or "")
correlated = _shortcut("correlated", DataGen.correlated.__doc__ or "")
choice_by = _shortcut("choice_by", DataGen.choice_by.__doc__ or "")
