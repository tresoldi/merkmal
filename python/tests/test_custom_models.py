"""Tests for bringing your own model and configuration from files."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import merkmal
from merkmal import paths
from merkmal.diacritics import DEFAULT_DIACRITICS, parse_diacritics

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _write_categorical_model(root: Path, name: str = "mymodel") -> Path:
    mdir = root / name
    mdir.mkdir()
    (mdir / "model.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": name,
                "version": "0.1.0",
                "type": "categorical",
                "description": "custom test model",
                "default_geometry": "clements-hume",
                "feature_extraction": "filtered",
            }
        )
    )
    (mdir / "inventory.tsv").write_text(
        "GRAPHEME\tNAME\nx\tvoiceless velar fricative consonant\n"
    )
    (mdir / "features.tsv").write_text(
        "VALUE\tFEATURE\n"
        "velar\tplace\nfricative\tmanner\nvoiceless\tphonation\nconsonant\ttype\n"
    )
    return mdir


def test_load_model_from_dir(tmp_path: Path) -> None:
    mdir = _write_categorical_model(tmp_path)
    system = merkmal.load_model_from_dir(mdir)
    assert system.name == "mymodel"
    assert system.grapheme_to_features("x") == frozenset(
        {"voiceless", "velar", "fricative", "consonant"}
    )


def test_register_dir_on_registry(tmp_path: Path) -> None:
    mdir = _write_categorical_model(tmp_path)
    registry = merkmal.create_registry()
    key = registry.register_dir(mdir)
    assert key == "mymodel"
    assert "mymodel" in registry.list_systems()
    # built-ins still present
    assert "descriptive" in registry.list_systems()


def test_env_layering_keeps_builtins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_categorical_model(tmp_path)
    monkeypatch.setenv("MERKMAL_MODELS", str(tmp_path))
    registry = merkmal.create_registry()
    assert "mymodel" in registry.list_systems()
    assert "descriptive" in registry.list_systems()


def test_isolation_excludes_builtins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_categorical_model(tmp_path)
    monkeypatch.setenv("MERKMAL_MODELS", str(tmp_path))
    monkeypatch.setenv("MERKMAL_DATA_ISOLATED", "1")
    registry = merkmal.create_registry(default_system="mymodel")
    assert registry.list_systems() == ["mymodel"]


def test_include_builtin_false_is_isolated(tmp_path: Path) -> None:
    _write_categorical_model(tmp_path)
    registry = merkmal.create_registry(
        register_builtin=False,
        default_system="mymodel",
        extra_model_dirs=[tmp_path],
    )
    assert registry.list_systems() == ["mymodel"]


def test_data_roots_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERKMAL_MODELS", str(tmp_path))
    roots = paths.data_roots("models")
    # env dir comes before bundled data
    assert roots[0].resolve() == tmp_path.resolve()
    assert len(roots) > 1


def test_bundled_diacritics_match_in_code_default() -> None:
    # The shipped ipa-clts.json must stay identical to the in-code default.
    path = paths.resolve_file("diacritics", "ipa-clts.json")
    assert path is not None
    parsed = parse_diacritics(json.loads(path.read_text(encoding="utf-8")), "ipa-clts")
    assert parsed.combining == DEFAULT_DIACRITICS.combining
    assert parsed.suffix == DEFAULT_DIACRITICS.suffix
    assert parsed.prefix == DEFAULT_DIACRITICS.prefix
    assert parsed.tone_marks == DEFAULT_DIACRITICS.tone_marks
    assert parsed.tone_onset == DEFAULT_DIACRITICS.tone_onset
    assert parsed.tone_mid == DEFAULT_DIACRITICS.tone_mid
    assert parsed.tone_offset == DEFAULT_DIACRITICS.tone_offset
    assert parsed.valued_effects == DEFAULT_DIACRITICS.valued_effects


def test_custom_diacritic_vocabulary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A model can declare its own diacritic set producing custom feature names.
    base = paths.resolve_file("diacritics", "ipa-clts.json")
    assert base is not None
    custom = json.loads(base.read_text(encoding="utf-8"))
    custom["name"] = "myipa"
    custom["suffix"]["02B0"] = "ASP"  # ʰ -> ASP instead of "aspirated"

    diac_dir = tmp_path / "diacritics"
    diac_dir.mkdir()
    (diac_dir / "myipa.json").write_text(json.dumps(custom))

    mdir = tmp_path / "mine"
    mdir.mkdir()
    (mdir / "model.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "mine",
                "version": "0.1.0",
                "type": "categorical",
                "default_geometry": "clements-hume",
                "feature_extraction": "filtered",
                "diacritics": "myipa",
            }
        )
    )
    (mdir / "inventory.tsv").write_text(
        "GRAPHEME\tNAME\nt\tvoiceless alveolar stop consonant\n"
    )
    (mdir / "features.tsv").write_text(
        "VALUE\tFEATURE\n"
        "alveolar\tplace\nstop\tmanner\nvoiceless\tphonation\nconsonant\ttype\n"
    )

    monkeypatch.setenv("MERKMAL_DIACRITICS", str(diac_dir))
    system = merkmal.load_model_from_dir(mdir)
    feats = system.grapheme_to_features("tʰ")
    assert feats is not None
    assert "ASP" in feats
    assert "aspirated" not in feats
