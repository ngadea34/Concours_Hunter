"""Interface des connecteurs (plugins). Ajouter un type = un module dans connectors/ avec @register."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import ClassVar

from ..db.models import Source
from .fetcher import Fetcher


@dataclass
class RawContest:
    title: str
    url: str  # page la plus proche de l'organisateur connue
    source_url: str  # page où la source l'a présenté
    detail_url: str | None = None
    description: str | None = None
    end_date: str | None = None  # ISO
    prize: str | None = None
    organizer: str | None = None
    rules_url: str | None = None
    entry_method: str | None = None
    language: str | None = None
    answers: list[tuple[str, str]] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


class Connector:
    kind: ClassVar[str] = ""
    description: ClassVar[str] = ""
    tos_note: ClassVar[str | None] = None
    default_config: ClassVar[dict] = {}

    def __init__(self, source: Source, fetcher: Fetcher):
        self.source = source
        self.fetcher = fetcher
        self.config = {**self.default_config, **(source.config or {})}

    def discover(self) -> Iterator[RawContest]:  # pragma: no cover - interface
        raise NotImplementedError


REGISTRY: dict[str, type[Connector]] = {}


def register(cls: type[Connector]) -> type[Connector]:
    REGISTRY[cls.kind] = cls
    return cls


def load_connectors() -> dict[str, type[Connector]]:
    import importlib
    import pkgutil

    from . import connectors

    for m in pkgutil.iter_modules(connectors.__path__):
        importlib.import_module(f"{connectors.__name__}.{m.name}")
    return REGISTRY
