"""Configurações dos geradores (modelos Pydantic imutáveis; parâmetro com nome errado vira erro)."""

from __future__ import annotations

from .address import AddressConfig, CepConfig, CityConfig, StateConfig
from .base import BaseConfig
from .business import CompanyConfig, OccupationConfig, VehicleConfig
from .choice import ChoiceConfig
from .contact import EmailConfig, PhoneConfig, UsernameConfig
from .documents import (
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
from .network import IPv4Config, IPv6Config, MACConfig, URLConfig, UUIDConfig
from .numbers import (
    BooleanConfig,
    DateConfig,
    DatetimeConfig,
    IntegerConfig,
    LognormalConfig,
    NormalConfig,
    UniformConfig,
)
from .person import AgeConfig, FirstNameConfig, FullNameConfig, LastNameConfig, SexConfig
from .relations import BirthdateConfig, ChoiceByConfig, CorrelatedConfig
from .text import ParagraphConfig, SentenceConfig

__all__ = [
    "AddressConfig",
    "AgeConfig",
    "BaseConfig",
    "BirthdateConfig",
    "BooleanConfig",
    "CNHConfig",
    "CNPJConfig",
    "CPFConfig",
    "CepConfig",
    "ChoiceByConfig",
    "ChoiceConfig",
    "CityConfig",
    "CompanyConfig",
    "CorrelatedConfig",
    "CreditCardConfig",
    "DateConfig",
    "DatetimeConfig",
    "EAN13Config",
    "EmailConfig",
    "FirstNameConfig",
    "FullNameConfig",
    "IBANConfig",
    "IPv4Config",
    "IPv6Config",
    "IntegerConfig",
    "LastNameConfig",
    "LicensePlateConfig",
    "LognormalConfig",
    "MACConfig",
    "NormalConfig",
    "OccupationConfig",
    "PISConfig",
    "ParagraphConfig",
    "PhoneConfig",
    "RGConfig",
    "SentenceConfig",
    "SexConfig",
    "StateConfig",
    "URLConfig",
    "UUIDConfig",
    "UniformConfig",
    "UsernameConfig",
    "VehicleConfig",
    "VoterIDConfig",
]
