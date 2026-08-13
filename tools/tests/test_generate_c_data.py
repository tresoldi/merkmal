"""Unit tests for the pieces of the generator that have no other check.

`scripts/check_generated_data.py` compares the emitter against its own output,
so it catches drift but not a consistently wrong emission. The string pool is
exactly that kind of risk: an off-by-one in an offset produces a file that
compiles, links, and names the wrong feature.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generate_c_data import (  # noqa: E402
    POOL_CHUNK,
    POOL_CHUNK_BITS,
    StringPool,
    c_string,
)


def read_back(pool: StringPool, offset: int) -> str:
    """Resolve an offset exactly as the generated mk_pool_string does."""
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
