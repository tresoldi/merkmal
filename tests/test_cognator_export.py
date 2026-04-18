"""Tests for the cognator export bundle."""

from __future__ import annotations

import hashlib
import json
import math
import os
import warnings
from typing import TYPE_CHECKING

import pytest

import merkmal
from merkmal.cognator_export import export_all_systems, export_cognator

if TYPE_CHECKING:
    from pathlib import Path


TEST_SYSTEM = "classfeat"
SYSTEMS_WITH_CLASSES: frozenset[str] = frozenset({"classfeat"})


def _read_tsv(path: Path) -> tuple[list[str], list[list[str]]]:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    assert lines[-1] == "", f"file {path} missing trailing newline"
    lines = lines[:-1]
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:]]
    return header, rows


def _run_export(
    tmp_path: Path,
    system: str = TEST_SYSTEM,
    *,
    force: bool = False,
) -> Path:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return export_cognator(system, tmp_path, force=force)


def test_export_produces_all_expected_files(tmp_path: Path) -> None:
    manifest_path = _run_export(tmp_path, "classfeat")
    for name in ("distances.tsv", "prosody.tsv", "fallback.tsv", "classes.tsv"):
        assert (tmp_path / name).exists(), f"missing {name}"
    assert manifest_path.exists()

    out2 = tmp_path / "sub"
    _run_export(out2, "descriptive")
    assert (out2 / "distances.tsv").exists()
    assert (out2 / "prosody.tsv").exists()
    assert (out2 / "fallback.tsv").exists()
    assert not (out2 / "classes.tsv").exists()


def test_distances_are_normalized(tmp_path: Path) -> None:
    _run_export(tmp_path, TEST_SYSTEM)
    _, rows = _read_tsv(tmp_path / "distances.tsv")
    seen_diagonal = False
    for a, b, d_str in rows:
        d = float(d_str)
        assert not math.isnan(d)
        assert not math.isinf(d)
        assert 0.0 <= d <= 1.0, f"{a}\t{b}\t{d}"
        if a == b:
            assert d == 0.0
            seen_diagonal = True
    assert seen_diagonal


def test_distance_symmetry_preserved(tmp_path: Path) -> None:
    _run_export(tmp_path, TEST_SYSTEM)
    _, rows = _read_tsv(tmp_path / "distances.tsv")
    lookup = {(a, b): float(d) for a, b, d in rows}
    for (a, b), d_ab in lookup.items():
        d_ba = lookup.get((b, a))
        assert d_ba is not None, f"missing reverse pair ({b!r}, {a!r})"
        assert abs(d_ab - d_ba) < 1e-9, f"asymmetric ({a!r}, {b!r})"


def test_classes_cover_inventory(tmp_path: Path) -> None:
    _run_export(tmp_path, TEST_SYSTEM)
    classes_path = tmp_path / "classes.tsv"
    assert classes_path.exists()
    _, class_rows = _read_tsv(classes_path)
    classes_graphemes = {row[0] for row in class_rows}

    _, prosody_rows = _read_tsv(tmp_path / "prosody.tsv")
    inventory = {row[0] for row in prosody_rows}
    assert inventory == classes_graphemes


def test_prosody_covers_inventory(tmp_path: Path) -> None:
    _run_export(tmp_path, TEST_SYSTEM)
    _, prosody_rows = _read_tsv(tmp_path / "prosody.tsv")
    graphemes_in_prosody = {row[0] for row in prosody_rows}

    _, dist_rows = _read_tsv(tmp_path / "distances.tsv")
    inventory = {row[0] for row in dist_rows}
    assert graphemes_in_prosody == inventory

    allowed = {"C", "R", "V", "G", "T", "S", "X"}
    for row in prosody_rows:
        assert row[1] in allowed

    x_count = sum(1 for row in prosody_rows if row[1] == "X")
    assert x_count == 0, f"classfeat unexpectedly produced {x_count} X roles"


def test_manifest_hashes_match(tmp_path: Path) -> None:
    _run_export(tmp_path, TEST_SYSTEM)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    for name, meta in manifest["files"].items():
        path = tmp_path / name
        if not meta["present"]:
            assert not path.exists()
            continue
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == meta["sha256"]
        assert len(data) == meta["bytes"]
        assert max(0, data.count(b"\n") - 1) == meta["rows"]


def test_byte_stable_under_source_date_epoch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    a = tmp_path / "a"
    b = tmp_path / "b"
    _run_export(a, TEST_SYSTEM)
    _run_export(b, TEST_SYSTEM)
    for name in ("distances.tsv", "classes.tsv", "prosody.tsv", "fallback.tsv", "manifest.json"):
        fa = a / name
        fb = b / name
        assert fa.exists() == fb.exists()
        if fa.exists():
            assert fa.read_bytes() == fb.read_bytes(), f"unstable: {name}"


@pytest.mark.skipif(
    not os.environ.get("MERKMAL_TEST_ALL_SYSTEMS"),
    reason="set MERKMAL_TEST_ALL_SYSTEMS=1 to run the full --all-systems export "
    "(slow: exports phoible's ~10M pairs).",
)
def test_all_systems_exportable(tmp_path: Path) -> None:
    root = tmp_path / "all"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        manifests = export_all_systems(root, force=True)

    available = merkmal.list_systems()
    assert len(manifests) == len(available)
    for system in available:
        sub = root / system
        assert (sub / "manifest.json").exists(), system
        assert (sub / "distances.tsv").exists(), system
        assert (sub / "prosody.tsv").exists(), system
        assert (sub / "fallback.tsv").exists(), system
        manifest = json.loads((sub / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["system"] == system
        assert manifest["schema_version"] == 1
        expected_classes = system in SYSTEMS_WITH_CLASSES
        assert manifest["files"]["classes.tsv"]["present"] == expected_classes


def test_round_trip_distance_parity(tmp_path: Path) -> None:
    _run_export(tmp_path, TEST_SYSTEM)
    _, rows = _read_tsv(tmp_path / "distances.tsv")
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    d_max_raw = float(manifest["distance_normalization"]["d_max_raw"])
    d_max_for_norm = d_max_raw if d_max_raw > 0.0 else 1.0

    loaded = {(a, b): float(d) for a, b, d in rows}
    assert len(loaded) == len(rows)
    for (a, b), loaded_d in loaded.items():
        if a == b:
            assert loaded_d == 0.0
            continue
        raw = merkmal.distance(a, b, system=TEST_SYSTEM)
        expected = max(0.0, min(1.0, raw / d_max_for_norm))
        assert abs(loaded_d - expected) < 1e-6, f"{a}\t{b}"


def test_fallback_tsv_header_only_when_empty(tmp_path: Path) -> None:
    _run_export(tmp_path, TEST_SYSTEM)
    text = (tmp_path / "fallback.tsv").read_text(encoding="utf-8")
    assert text == "input\ttarget\tnote\n"


def test_non_empty_dir_without_force_raises(tmp_path: Path) -> None:
    (tmp_path / "stale.txt").write_text("preexisting")
    with pytest.raises(FileExistsError):
        export_cognator(TEST_SYSTEM, tmp_path, force=False)
    # force=True succeeds
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        export_cognator(TEST_SYSTEM, tmp_path, force=True)
    assert (tmp_path / "manifest.json").exists()


def test_unknown_system_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        export_cognator("not-a-real-system", tmp_path)


def test_export_date_pinned_by_source_date_epoch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    _run_export(tmp_path, TEST_SYSTEM)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["export_date"] == "2023-11-14T22:13:20Z"
