"""Documentos brasileiros e códigos: CPF, CNPJ, PIS, título, CNH, RG, placa, cartão, IBAN, EAN-13.

Todos os textos saem do C++ já prontos nas views do Arrow (`TextJob`); os que têm até 12 caracteres moram na própria
view, sem buffer de texto.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .._native import lib
from ..config.documents import (
    CNHConfig,
    CNPJConfig,
    CPFConfig,
    CreditCardConfig,
    EAN13Config,
    IBANConfig,
    LicensePlateConfig,
    PISConfig,
    RGConfig,
    VoterIDConfig,
)
from ..core.blocks import BLOCK_ROWS
from ..core.rng import stream_words
from ..registry import registry
from .base import Job, Provider, Run, TextJob

__all__ = ["id_job"]

CPF_SPACE = 10**9  # dígitos-base do CPF


def id_job(run: Run, kind: int, style: int, stride: int) -> TextJob:
    """Job do kernel genérico de identificadores (`dg_id_views`)."""
    fn = lib().dg_id_views
    return TextJob(run.n, stride, lambda st, m, v, d, _: fn(st, kind, style, m, v, d, stride), len(run.blocks))


def _unique_too_big(n: int, space: int, what: str) -> None:
    if n > space:
        raise ValueError(f"unique=True permite no máximo {space:,} {what} nesta configuração (pedidos: {n:,})")


@registry.register
class CPFProvider(Provider[CPFConfig]):
    kind = "cpf"
    config_cls = CPFConfig
    ns_per_row = 5.0

    def plan(self, run: Run, config: CPFConfig, inputs: Mapping[str, Any]) -> Job:
        fmt = int(config.formatted)
        stride = 16 if config.formatted else 0
        if not config.unique:
            rnd = lib().dg_cpf_random
            return TextJob(run.n, stride, lambda st, m, v, d, _: rnd(st, m, fmt, v, d), len(run.blocks))
        _unique_too_big(run.n, CPF_SPACE, "CPFs")
        key, perm = unique_key(run), lib().dg_cpf_perm
        # linha global i -> base perm(i): cada bloco só precisa da sua primeira linha (independe das threads)
        return TextJob(run.n, stride, lambda st, m, v, d, start: perm(key, start, m, fmt, v, d), len(run.blocks))


def unique_key(run: Run) -> int:
    """Chave de 64 bits da permutação sem repetição, tirada da semente e do nome da coluna."""
    return stream_words(run.ctx.seed, run.name + ":unique", 1)[0]


@registry.register
class CNPJProvider(Provider[CNPJConfig]):
    kind = "cnpj"
    config_cls = CNPJConfig
    ns_per_row = 11.0

    def plan(self, run: Run, config: CNPJConfig, inputs: Mapping[str, Any]) -> Job:
        k = 36 if config.alphanumeric else 10
        if config.branch is not None:
            idx = [_cnpj_index(c) for c in config.branch]
            tp4, tp5 = idx[0] * k + idx[1], idx[2] * k + idx[3]
            space = k**8
        else:
            tp4 = tp5 = 0xFFFFFFFF
            space = k**12
        fmt, stride = int(config.formatted), 18 if config.formatted else 14
        gen = lib().dg_cnpj_gen
        if not config.unique:
            return TextJob(
                run.n, stride, lambda st, m, v, d, _: gen(st, k, tp4, tp5, fmt, 0, 0, 0, m, v, d), len(run.blocks)
            )
        _unique_too_big(run.n, space, "CNPJs")
        key = unique_key(run)
        return TextJob(
            run.n, stride, lambda st, m, v, d, start: gen(st, k, tp4, tp5, fmt, 1, start, key, m, v, d), len(run.blocks)
        )


def _cnpj_index(c: str) -> int:
    """Caractere da ordem -> índice no alfabeto do kernel (0-9, depois A-Z = 10-35); o config já validou."""
    return ord(c) - 48 if c.isdigit() else ord(c) - 55


@registry.register
class PISProvider(Provider[PISConfig]):
    kind = "pis"
    config_cls = PISConfig
    ns_per_row = 8.0

    def plan(self, run: Run, config: PISConfig, inputs: Mapping[str, Any]) -> Job:
        return id_job(run, 0, int(config.formatted), 16 if config.formatted else 0)


@registry.register
class VoterIDProvider(Provider[VoterIDConfig]):
    kind = "voter_id"
    config_cls = VoterIDConfig
    ns_per_row = 11.0

    def plan(self, run: Run, config: VoterIDConfig, inputs: Mapping[str, Any]) -> Job:
        return id_job(run, 1, int(config.formatted), 16 if config.formatted else 0)


@registry.register
class CNHProvider(Provider[CNHConfig]):
    kind = "cnh"
    config_cls = CNHConfig
    ns_per_row = 10.0

    def plan(self, run: Run, config: CNHConfig, inputs: Mapping[str, Any]) -> Job:
        return id_job(run, 2, 0, 0)


@registry.register
class RGProvider(Provider[RGConfig]):
    kind = "rg"
    config_cls = RGConfig
    ns_per_row = 10.0

    def plan(self, run: Run, config: RGConfig, inputs: Mapping[str, Any]) -> Job:
        return id_job(run, 5, int(config.formatted), 0)  # "12.345.678-9" tem 12 caracteres: cabe na view


@registry.register
class LicensePlateProvider(Provider[LicensePlateConfig]):
    kind = "license_plate"
    config_cls = LicensePlateConfig
    ns_per_row = 5.0

    def plan(self, run: Run, config: LicensePlateConfig, inputs: Mapping[str, Any]) -> Job:
        return id_job(run, 3 if config.style == "mercosul" else 4, 0, 0)


_BRANDS = {"visa": 0, "mastercard": 1, "amex": 2, "mixed": 3}


@registry.register
class CreditCardProvider(Provider[CreditCardConfig]):
    kind = "credit_card"
    config_cls = CreditCardConfig
    ns_per_row = 15.0

    def plan(self, run: Run, config: CreditCardConfig, inputs: Mapping[str, Any]) -> Job:
        style = _BRANDS[config.brand] + 4 * int(config.formatted)
        return id_job(run, 11, style, 24 if config.formatted else 16)


@registry.register
class IBANProvider(Provider[IBANConfig]):
    kind = "iban"
    config_cls = IBANConfig
    ns_per_row = 15.0

    def plan(self, run: Run, config: IBANConfig, inputs: Mapping[str, Any]) -> Job:
        return id_job(run, 12, 0, 32)


@registry.register
class EAN13Provider(Provider[EAN13Config]):
    kind = "ean13"
    config_cls = EAN13Config
    ns_per_row = 10.0

    def plan(self, run: Run, config: EAN13Config, inputs: Mapping[str, Any]) -> Job:
        return id_job(run, 13, 0, 16)


assert BLOCK_ROWS * 18 < 2**32  # deslocamentos de 32 bits nas views (maior stride por linha: 18 do CNPJ formatado)
