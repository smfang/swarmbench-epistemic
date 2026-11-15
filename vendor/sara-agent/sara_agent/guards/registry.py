"""Name->factory guard registry (from guardeval). The swap point: a new backend
is one file that self-registers, with no change to callers."""

from __future__ import annotations

from typing import Callable

from sara_agent.guards.base import GuardModel

_REGISTRY: dict[str, Callable[..., GuardModel]] = {}


def register(name: str, factory: Callable[..., GuardModel]) -> None:
    existing = _REGISTRY.get(name)
    if existing is not None and existing is not factory:
        raise ValueError(f"guard name already registered with a different factory: {name!r}")
    _REGISTRY[name] = factory


def get_guard(name: str, **cfg) -> GuardModel:
    if name not in _REGISTRY:
        raise KeyError(f"unknown guard {name!r}. Registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name](**cfg)


def list_guards() -> list[str]:
    return sorted(_REGISTRY)
