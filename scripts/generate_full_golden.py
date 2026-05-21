#!/usr/bin/env python3
"""Generate comprehensive golden parity data for all models.

Produces {model}_features_full.tsv for every model, covering:
  - All inventory graphemes
  - A set of probe graphemes (modified forms, affricates, etc.)

Also produces probe_distances.tsv with distances for probe graphemes
across all models that resolve them.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from merkmal.model import list_available_models, load_model

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden"

PROBE_GRAPHEMES = [
    "pʰ", "bʰ", "tʰ", "dʰ", "kʰ", "gʰ",
    "n̥", "m̥", "l̥", "r̥", "ŋ̥",
    "ã", "ẽ", "ĩ", "õ", "ũ",
    "aː", "eː", "iː", "oː", "uː", "pː", "tː", "kː",
    "t͡s", "d͡z", "t͡ʃ", "d͡ʒ", "tʃ", "dʒ", "ts", "dz",
    "pʼ", "tʼ", "kʼ", "t͡sʼ",
    "ⁿd", "ⁿb", "ⁿg",
    "pʷ", "tʷ", "kʷ", "bʷ", "dʷ", "gʷ",
    "pʲ", "tʲ", "kʲ", "bʲ", "dʲ", "gʲ",
    "n̩", "m̩", "l̩",
    "k͡p", "g͡b",
    "t̪", "d̪", "n̪",
    "ɡ̊", "b̥", "d̥", "g̥",
]

PROBE_PAIRS = [
    ("p", "b"), ("p", "t"), ("p", "k"), ("t", "d"), ("t", "s"),
    ("p", "pʰ"), ("t", "tʰ"), ("k", "kʰ"),
    ("n", "n̥"), ("m", "m̥"),
    ("a", "ã"), ("a", "aː"),
    ("t͡s", "s"), ("t͡ʃ", "ʃ"),
    ("p", "a"), ("i", "u"), ("a", "i"),
    ("pʼ", "p"), ("tʼ", "t"),
]


def generate_features(model_name: str, sys_obj: object) -> int:
    graphemes = list(sys_obj.list_graphemes())
    all_graphemes = sorted(set(graphemes) | set(PROBE_GRAPHEMES))

    path = GOLDEN_DIR / f"{model_name}_features_full.tsv"
    count = 0
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["GRAPHEME", "FEATURES"])
        for g in all_graphemes:
            feats = sys_obj.grapheme_to_features(g)
            if feats is not None:
                writer.writerow([g, "|".join(sorted(feats))])
                count += 1
    return count


def generate_distances(model_name: str, sys_obj: object) -> int:
    path = GOLDEN_DIR / f"{model_name}_distances_full.tsv"
    count = 0
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["GRAPHEME_A", "GRAPHEME_B", "DISTANCE"])
        for a, b in PROBE_PAIRS:
            if model_name == "classfeat":
                try:
                    d = sys_obj.grapheme_cost(a, b)
                except Exception:
                    continue
            else:
                rep_a = sys_obj.grapheme_to_representation(a)
                rep_b = sys_obj.grapheme_to_representation(b)
                if rep_a is None or rep_b is None:
                    continue
                d = sys_obj.segment_distance(rep_a, rep_b)
            writer.writerow([a, b, f"{d}"])
            count += 1
    return count


def main() -> None:
    models = sorted(list_available_models())
    for name in models:
        sys_obj = load_model(name)
        feat_count = generate_features(name, sys_obj)
        dist_count = generate_distances(name, sys_obj)
        print(f"{name}: {feat_count} features, {dist_count} distances", file=sys.stderr)
    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
