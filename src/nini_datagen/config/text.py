"""Configurações dos geradores de texto por gramática: frase e parágrafo."""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from .base import BaseConfig

__all__ = ["ParagraphConfig", "SentenceConfig"]

Option = str | tuple[str, float]


class SentenceConfig(BaseConfig):
    """Frases em português montadas por uma gramática com concordância (sem sentido de verdade, mas plausíveis).

    * ``theme``: tema do locale (no pt_BR: ``"atendimento"``, ``"saude"``, ``"entrega"``, ``"avaliacao"``,
      ``"cadastro"``) ou ``"geral"`` (todos; o tema é sorteado por linha).
    * ``templates``: modelos próprios, ex. ``["Pedido {d}{d}{d} enviado {prazo}.", ("Sem observações.", 3)]``; os
      ``{slots}`` podem ser os comuns do locale (``{valor}``, ``{protocolo}``, ``{tempo}``, ``{canal}``, ``{prazo}``,
      ``{d}``...) ou os de ``slots``.
    * ``slots``: ``{nome: [opções]}`` usados pelos modelos (e entre si); opção = texto ou ``(texto, peso)``.
    """

    theme: str = "geral"
    templates: tuple[Option, ...] | None = Field(default=None, min_length=1)
    slots: tuple[tuple[str, tuple[Option, ...]], ...] | None = None

    @field_validator("slots", mode="before")
    @classmethod
    def _slots_from_dict(cls, v: Any) -> Any:
        # dict vira tupla de pares: a configuração continua imutável e com hash
        if isinstance(v, dict):
            return tuple((k, tuple(opts)) for k, opts in v.items())
        return v

    @model_validator(mode="after")
    def _templates_or_root(self) -> SentenceConfig:
        if self.slots is not None and self.templates is None and "frase" not in dict(self.slots):
            raise ValueError("com slots, passe templates (ou um slot 'frase')")
        return self

    @property
    def sentence_range(self) -> tuple[int, int]:
        return (1, 1)


class ParagraphConfig(SentenceConfig):
    """Parágrafos: ``sentences=(mín, máx)`` frases da mesma gramática de `SentenceConfig` (com ``theme="geral"``, o
    tema é o mesmo no parágrafo inteiro)."""

    sentences: tuple[int, int] = (3, 6)

    @field_validator("sentences")
    @classmethod
    def _range(cls, v: tuple[int, int]) -> tuple[int, int]:
        if not 1 <= v[0] <= v[1] <= 100:
            raise ValueError("sentences deve ser (mín, máx) com 1 <= mín <= máx <= 100")
        return v

    @property
    def sentence_range(self) -> tuple[int, int]:
        return self.sentences
