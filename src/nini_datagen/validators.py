"""Validadores dos documentos e códigos gerados (dígitos verificadores), para uso em testes e em dados de terceiros.

Cada função recebe um texto (formatado ou não) e devolve ``True`` se o formato e os dígitos verificadores conferem.
Pontuação é ignorada (``"123.456.789-09"`` e ``"12345678909"`` valem igual); letras só onde o documento admite.

>>> from nini_datagen import validators
>>> validators.cpf("529.982.247-25")
True
"""

from __future__ import annotations

import re

__all__ = ["cnh", "cnpj", "cpf", "credit_card", "ean13", "iban", "pis", "rg", "voter_id"]

_PUNCT = re.compile(r"[\s.\-/]")


def _clean(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return _PUNCT.sub("", value).upper()


def _digits(value: object, n: int) -> list[int] | None:
    s = _clean(value)
    if s is None or len(s) != n or not s.isascii() or not s.isdigit():
        return None
    return [ord(c) - 48 for c in s]


def _mod11(digits: list[int], weights: range | list[int]) -> int:
    r = sum(d * w for d, w in zip(digits, weights, strict=True)) % 11
    return 0 if r < 2 else 11 - r


def cpf(value: object) -> bool:
    """CPF: 11 dígitos, 2 DV módulo 11. Sequências de um dígito só (``000.000.000-00``...) são inválidas."""
    d = _digits(value, 11)
    if d is None or len(set(d)) == 1:
        return False
    return _mod11(d[:9], range(10, 1, -1)) == d[9] and _mod11(d[:10], range(11, 1, -1)) == d[10]


_CNPJ_W1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_CNPJ_W2 = [6, *_CNPJ_W1]


def cnpj(value: object) -> bool:
    """CNPJ numérico ou alfanumérico: 12 caracteres 0-9/A-Z + 2 DV numéricos (valor de cada caractere = ASCII - 48)."""
    s = _clean(value)
    if s is None or len(s) != 14 or not s.isascii() or not s.isalnum() or not s[12:].isdigit():
        return False
    v = [ord(c) - 48 for c in s]
    if len(set(s)) == 1:
        return False
    d1 = _mod11(v[:12], _CNPJ_W1)
    return d1 == v[12] and _mod11([*v[:12], d1], _CNPJ_W2) == v[13]


def pis(value: object) -> bool:
    """PIS/PASEP/NIS: 11 dígitos, DV módulo 11 com pesos 3,2,9,8,7,6,5,4,3,2."""
    d = _digits(value, 11)
    if d is None:
        return False
    r = 11 - sum(x * w for x, w in zip(d[:10], [3, 2, 9, 8, 7, 6, 5, 4, 3, 2], strict=True)) % 11
    return (0 if r >= 10 else r) == d[10]


def voter_id(value: object) -> bool:
    """Título de eleitor: 8 dígitos de sequência + UF (01-28) + 2 DV (resto 10 -> 0).

    Para SP e MG (UF 01 e 02) aceita as duas leituras em uso para resto 0 (DV 0 pela Resolução TSE, DV 1 pela regra
    usual).
    """
    d = _digits(value, 12)
    if d is None:
        return False
    uf = d[8] * 10 + d[9]
    if not 1 <= uf <= 28:
        return False
    r1 = sum(x * w for x, w in zip(d[:8], range(2, 10), strict=True)) % 11
    r2 = (d[8] * 7 + d[9] * 8 + d[10] * 9) % 11
    ok1 = {0 if r1 == 10 else r1} | ({1} if uf <= 2 and r1 == 0 else set())
    ok2 = {0 if r2 == 10 else r2} | ({1} if uf <= 2 and r2 == 0 else set())
    return d[10] in ok1 and d[11] in ok2


def cnh(value: object) -> bool:
    """Registro da CNH: 11 dígitos, 2 DV (DENATRAN)."""
    d = _digits(value, 11)
    if d is None or len(set(d)) == 1:
        return False
    v1 = sum(x * w for x, w in zip(d[:9], range(9, 0, -1), strict=True))
    dsc, d1 = 0, v1 % 11
    if d1 >= 10:
        d1, dsc = 0, 2
    d2 = (sum(x * w for x, w in zip(d[:9], range(1, 10), strict=True)) % 11 - dsc) % 11
    if d2 >= 10:
        d2 = 0
    return d1 == d[9] and d2 == d[10]


def rg(value: object) -> bool:
    """RG no padrão de SP: 8 dígitos + DV (pesos 2 a 9; 11 - resto, 10 -> X, 11 -> 0)."""
    s = _clean(value)
    if s is None or len(s) != 9 or not s.isascii() or not s[:8].isdigit():
        return False
    dv = 11 - sum((ord(c) - 48) * w for c, w in zip(s[:8], range(2, 10), strict=True)) % 11
    return s[8] == ("X" if dv == 10 else "0" if dv == 11 else str(dv))


def credit_card(value: object) -> bool:
    """Número de cartão (12 a 19 dígitos) com dígito de Luhn correto."""
    s = _clean(value)
    if s is None or not 12 <= len(s) <= 19 or not s.isascii() or not s.isdigit():
        return False
    total = 0
    for i, c in enumerate(reversed(s)):
        t = ord(c) - 48
        if i % 2:
            t = t * 2 - 9 if t > 4 else t * 2
        total += t
    return total % 10 == 0


def iban(value: object) -> bool:
    """IBAN (qualquer país): 2 letras + 2 DV + até 30 caracteres alfanuméricos, módulo 97 == 1."""
    s = _clean(value)
    if s is None or not 15 <= len(s) <= 34 or not s.isascii() or not s.isalnum():
        return False
    if not (s[:2].isalpha() and s[2:4].isdigit()):
        return False
    rearranged = s[4:] + s[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def ean13(value: object) -> bool:
    """EAN-13: 13 dígitos, DV com pesos 1 e 3 alternados."""
    d = _digits(value, 13)
    if d is None:
        return False
    return (10 - sum(x * (3 if i % 2 else 1) for i, x in enumerate(d[:12])) % 10) % 10 == d[12]
