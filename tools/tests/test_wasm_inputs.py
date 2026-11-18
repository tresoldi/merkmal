"""Unit tests for the WebAssembly input hash."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wasm_inputs  # noqa: E402


def test_inputs_cover_the_adapter_and_the_full_profile_only() -> None:
    names = {path.relative_to(wasm_inputs.ROOT).as_posix() for path in wasm_inputs.inputs()}
    assert "web/merkmal_wasm.c" in names
    assert "include/merkmal.h" in names
    assert "src/generated/builtin_data.c" in names
    assert not any("cc-by" in name for name in names)


def test_hash_changes_with_any_input(tmp_path, monkeypatch) -> None:
    before = wasm_inputs.inputs_sha256()
    first = wasm_inputs.inputs()[0]
    copy = tmp_path / "copy"
    copy.write_bytes(first.read_bytes() + b"\n")
    original = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        return original(copy) if path == first else original(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    assert wasm_inputs.inputs_sha256() != before
