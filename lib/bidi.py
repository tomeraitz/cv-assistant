"""Minimal, vendored bidirectional-text reordering for RTL rendering.

python-bidi is LGPL and its current releases require a Rust toolchain to build;
to keep this offline-friendly and license-clean we vendor a compact subset of
the Unicode Bidirectional Algorithm (UAX #9) covering our scope: a base-RTL
paragraph (Hebrew/Arabic) with embedded LTR runs (Latin tech proper-nouns such
as "Python") and European numbers. Text is reordered logical -> visual for a
right-to-left base direction.

This is intentionally not a full UAX #9 implementation (no explicit
embeddings/overrides, no isolates); it handles the resume cases we render:
strong R/L runs, European/Arabic numbers, and common neutrals.

`get_display(text, base_dir="R")` returns the visually-reordered string, mirror
of python-bidi's API so call sites can swap implementations.
"""

from __future__ import annotations

import unicodedata

_R = "R"
_L = "L"


def _strong_dir(ch: str) -> str | None:
    """Strong bidi class of a char: 'R', 'L', or None for non-strong."""
    bc = unicodedata.bidirectional(ch)
    if bc in ("R", "AL"):
        return _R
    if bc == "L":
        return _L
    return None


def _char_type(ch: str) -> str:
    """Coarse bidi type: 'R', 'L', 'EN' (number), or 'N' (neutral)."""
    bc = unicodedata.bidirectional(ch)
    if bc in ("R", "AL"):
        return _R
    if bc == "L":
        return _L
    if bc in ("EN", "AN"):
        return "EN"
    return "N"


def _resolve_levels(text: str, base_level: int) -> list[int]:
    """Assign an embedding level to each char (even=LTR, odd=RTL).

    Simplified resolution: neutrals take the direction of the surrounding
    strong context (or base if it would otherwise be ambiguous); European
    numbers render LTR but, in an RTL base, sit at an even level just above the
    base so the digits stay in logical order while the run flows right-to-left.
    """
    n = len(text)
    types = [_char_type(c) for c in text]
    levels = [base_level] * n

    # Resolve neutrals to the surrounding strong type (sor/eor = base dir).
    base_type = _R if base_level % 2 else _L
    i = 0
    while i < n:
        if types[i] == "N":
            j = i
            while j < n and types[j] == "N":
                j += 1
            prev = types[i - 1] if i > 0 else base_type
            nxt = types[j] if j < n else base_type
            prev = "R" if prev in ("R",) else ("L" if prev in ("L", "EN") else base_type)
            nxt = "R" if nxt in ("R",) else ("L" if nxt in ("L", "EN") else base_type)
            resolved = prev if prev == nxt else base_type
            for k in range(i, j):
                types[k] = resolved
            i = j
        else:
            i += 1

    if base_level % 2:  # RTL base (odd)
        # R content stays at the base (odd) level; L runs and numbers move up
        # to base+1 (even) so their internal order survives the L2 reversal.
        for i, t in enumerate(types):
            levels[i] = base_level + 1 if t in ("L", "EN") else base_level
    else:  # LTR base (even)
        for i, t in enumerate(types):
            levels[i] = base_level + 1 if t == "R" else base_level
    return levels


def _reorder(text: str, levels: list[int], base_level: int) -> str:
    """Apply the UAX #9 L2 reversal: reverse contiguous runs from the highest
    level down to the lowest odd level."""
    chars = list(text)
    if not chars:
        return ""
    max_level = max(levels)
    min_odd = min((lv for lv in levels if lv % 2), default=max_level + 1)
    for level in range(max_level, min_odd - 1, -1):
        i = 0
        n = len(chars)
        while i < n:
            if levels[i] >= level:
                j = i
                while j < n and levels[j] >= level:
                    j += 1
                chars[i:j] = chars[i:j][::-1]
                levels[i:j] = levels[i:j][::-1]
                i = j
            else:
                i += 1
    return "".join(chars)


def get_display(text: str, base_dir: str = "R") -> str:
    """Reorder `text` from logical to visual order for the given base direction.

    base_dir: "R" for right-to-left base, "L" for left-to-right.
    """
    if not text:
        return text
    base_level = 1 if base_dir.upper() == "R" else 0
    levels = _resolve_levels(text, base_level)
    return _reorder(text, levels, base_level)


def has_rtl(text: str) -> bool:
    """True if `text` contains any strong right-to-left character."""
    return any(_strong_dir(ch) == _R for ch in text)
