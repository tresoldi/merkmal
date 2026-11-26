"""Unit tests for the pieces of the generator that have no other check.

`tools/check_generated_data.py` compares the emitter against its own output,
so it catches drift but not a consistently wrong emission. The string pool is
exactly that kind of risk: an off-by-one in an offset produces a file that
compiles, links, and names the wrong feature.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import generate_c_data  # noqa: E402
from generate_c_data import (  # noqa: E402
    POOL_CHUNK,
    POOL_CHUNK_BITS,
    StringPool,
    c_string,
)


def read_back(pool: StringPool, offset: int) -> str:
    """Resolve an offset exactly as the generated mki_pool_string does."""
    chunk = pool.chunks[offset >> POOL_CHUNK_BITS]
    local = offset & (POOL_CHUNK - 1)
    end = chunk.index(b"\0", local)
    return chunk[local:end].decode("utf-8")


def test_offsets_round_trip():
    pool = StringPool()
    values = ["voice", "voiced", "voiceless", "a", ""]
    offsets = [pool.add(v) for v in values]
    for value, offset in zip(values, offsets, strict=True):
        assert read_back(pool, offset) == value


def test_repeated_values_share_one_offset():
    pool = StringPool()
    first = pool.add("nasal")
    pool.add("lateral")
    assert pool.add("nasal") == first


def test_non_ascii_offsets_are_byte_offsets():
    # A character offset would put every grapheme after the first non-ASCII one
    # at the wrong index, and the failure would look like a wrong feature name
    # rather than a crash.
    pool = StringPool()
    first = pool.add("tʃ")
    second = pool.add("after")
    assert second - first == len("tʃ".encode()) + 1
    assert read_back(pool, second) == "after"


def test_strings_never_straddle_a_chunk():
    pool = StringPool()
    # Fill past one chunk boundary with values that do not divide it evenly.
    values = [f"feature-{index:04d}-padding" for index in range(400)]
    offsets = [pool.add(v) for v in values]
    assert len(pool.chunks) > 1, "test did not cross a chunk boundary"
    for value, offset in zip(values, offsets, strict=True):
        assert read_back(pool, offset) == value
        assert (offset & (POOL_CHUNK - 1)) + len(value.encode("utf-8")) < POOL_CHUNK


def test_emitted_chunks_stay_under_the_c99_literal_limit():
    pool = StringPool()
    for index in range(500):
        pool.add(f"label-{index:04d}")
    emitted = pool.emit("mk_pool")
    # Adjacent literals concatenate into one, so the per-chunk total is what
    # C99 limits to 4095 characters.
    for block in emitted.split("static const char mk_pool_")[1:]:
        body = block.split("=", 1)[1].split(";", 1)[0]
        literal_chars = sum(
            len(line.strip().strip('"')) for line in body.splitlines() if line.strip()
        )
        assert literal_chars < 4095


def test_oversized_entry_is_rejected():
    pool = StringPool()
    with pytest.raises(SystemExit):
        pool.add("x" * (POOL_CHUNK + 1))


def test_c_string_escapes_quotes_and_backslashes():
    assert c_string('a"b') == '"a\\"b"'
    assert c_string("a\\b") == '"a\\\\b"'


def test_runtime_derivation_matches_the_generator() -> None:
    # src/classes.c derives class and articulator labels for feature sets built
    # at run time; the generator derives them for compiled rows. A runtime
    # model holding each compiled row's underived labels must resolve to the
    # compiled row, or the two derivations have drifted apart.
    import csv

    import merkmal

    for system in ("distinctive", "descriptive"):
        model_dir = generate_c_data.ROOT / "data" / "models" / system
        raw = json.loads((model_dir / "model.json").read_text(encoding="utf-8"))
        filtered = raw.get("feature_extraction", "") == "filtered"
        categories: dict[str, str] = {}
        features_path = model_dir / "features.tsv"
        if features_path.exists():
            with features_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.reader(handle, delimiter="\t"))[1:]
            categories = {row[0]: row[1] for row in rows if len(row) >= 2}
        with (model_dir / "inventory.tsv").open(encoding="utf-8", newline="") as handle:
            inventory = [row for row in list(csv.reader(handle, delimiter="\t"))[1:] if len(row) >= 2]

        lines = ["@model derivation-check", "@type categorical", "@validation permissive"]
        expected: dict[str, frozenset[str]] = {}
        for grapheme, name in inventory:
            labels = generate_c_data.parse_sound_name(name, categories, filtered)
            key = generate_c_data.normalize_input_grapheme(grapheme)
            if not labels or key in expected or any(c.isspace() for c in key):
                continue
            expected[key] = frozenset(merkmal.get_features(grapheme, system=system))
            lines.append(f"grapheme {key} " + " ".join(sorted(labels)))

        registry = merkmal.Registry()
        registry.add_model_text("\n".join(lines) + "\n")
        mismatched = [
            key
            for key, features in expected.items()
            if frozenset(registry.get_features(key, system="derivation-check")) != features
        ]
        assert not mismatched, f"{system}: {len(mismatched)} rows differ, e.g. {mismatched[:5]}"
