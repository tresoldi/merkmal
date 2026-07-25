"""Tests for registry APIs."""

from merkmal import (
    Registry,
    get_registry,
    get_system,
    list_systems,
    reset_registry,
    set_default,
)
from merkmal.registry import create_registry


def test_registry_creation() -> None:
    registry = create_registry()
    assert isinstance(registry, Registry)
    assert "descriptive" in registry.list_systems()
    assert "pbase-hc" in registry.list_systems()


def test_lazy_default_registry() -> None:
    reset_registry()
    assert "descriptive" in list_systems()
    assert "pbase-hc" in list_systems()
    assert get_registry().get_system().name == "descriptive"


def test_set_default() -> None:
    reset_registry()
    set_default("broad")
    assert get_system().name == "broad"
    set_default("descriptive")


def test_explicit_registry_is_isolated() -> None:
    registry = Registry()
    assert registry.list_systems() == []
