"""Font resolution for multi-language PDF rendering.

The PDF step re-inserts replacement text on the user's source resume. To support
any language we:

- derive *script* and *script direction* (LTR/RTL) deterministically from each
  run's Unicode code points (no language guessing);
- reuse the font already embedded in the source PDF per text run (matches the
  resume's own typeface, covers its language "for free");
- fall back to a bundled Noto font for the run's script when the embedded font
  lacks a needed glyph (common with subsetted CJK fonts) — the *glyph fallback*.

This module owns the bundled-asset layer and the script/direction classifier.
Embedded-font extraction and per-run resolution build on top of it.

See ADR docs/adr/0001 and CONTEXT.md (*target language*, *script direction*,
*glyph fallback*).
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from pathlib import Path

import fitz

logger = logging.getLogger(__name__)

# Bundled Noto fonts live at <project>/assets/fonts. This module is
# <project>/lib/fonts.py, so the assets dir is one parent up + assets/fonts.
_FONTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"


class BundledFont(enum.Enum):
    """A bundled Noto font family, keyed by the script it covers."""

    LATIN = "latin"
    HEBREW = "hebrew"
    CJK = "cjk"


# (regular, bold) filenames per bundled family.
_BUNDLED_FILES: dict[BundledFont, tuple[str, str]] = {
    BundledFont.LATIN: ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf"),
    BundledFont.HEBREW: ("NotoSansHebrew-Regular.ttf", "NotoSansHebrew-Bold.ttf"),
    BundledFont.CJK: ("NotoSansSC-Regular.otf", "NotoSansSC-Bold.otf"),
}


def bundled_font_path(font: BundledFont, *, bold: bool = False) -> str:
    """Return the absolute path to a bundled Noto font file.

    Raises FileNotFoundError if the asset is missing (e.g. not packaged).
    """
    regular, bold_file = _BUNDLED_FILES[font]
    name = bold_file if bold else regular
    path = _FONTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Bundled font asset not found: {path}")
    return str(path)


# ── Script & direction classification ──
#
# Derived deterministically from Unicode code points, per run — never from a
# language-detection guess (ADR-0001). Hebrew/Arabic are RTL; everything else
# we render is LTR.


class Script(enum.Enum):
    """The writing system of a text run (drives font + direction choice)."""

    LATIN = "latin"
    HEBREW = "hebrew"
    ARABIC = "arabic"
    CJK = "cjk"
    CYRILLIC = "cyrillic"
    GREEK = "greek"
    COMMON = "common"  # digits, punctuation, spaces — no script of their own


class Direction(enum.Enum):
    LTR = "ltr"
    RTL = "rtl"


# Contiguous Unicode ranges per script, in priority order. CJK spans several
# blocks (CJK Unified, Hiragana/Katakana, Hangul, CJK ext-A, compatibility).
_SCRIPT_RANGES: list[tuple[int, int, Script]] = [
    (0x0590, 0x05FF, Script.HEBREW),       # Hebrew
    (0xFB1D, 0xFB4F, Script.HEBREW),       # Hebrew presentation forms
    (0x0600, 0x06FF, Script.ARABIC),       # Arabic
    (0x0750, 0x077F, Script.ARABIC),       # Arabic supplement
    (0x08A0, 0x08FF, Script.ARABIC),       # Arabic extended-A
    (0xFB50, 0xFDFF, Script.ARABIC),       # Arabic presentation forms-A
    (0xFE70, 0xFEFF, Script.ARABIC),       # Arabic presentation forms-B
    (0x0400, 0x04FF, Script.CYRILLIC),     # Cyrillic
    (0x0500, 0x052F, Script.CYRILLIC),     # Cyrillic supplement
    (0x0370, 0x03FF, Script.GREEK),        # Greek and Coptic
    (0x1F00, 0x1FFF, Script.GREEK),        # Greek extended
    (0x3040, 0x30FF, Script.CJK),          # Hiragana + Katakana
    (0x3400, 0x4DBF, Script.CJK),          # CJK ext-A
    (0x4E00, 0x9FFF, Script.CJK),          # CJK Unified Ideographs
    (0xF900, 0xFAFF, Script.CJK),          # CJK compatibility ideographs
    (0xAC00, 0xD7AF, Script.CJK),          # Hangul syllables
    (0x0041, 0x024F, Script.LATIN),        # Basic Latin letters + Latin-1/ext
    (0x1E00, 0x1EFF, Script.LATIN),        # Latin extended additional
]

_RTL_SCRIPTS = frozenset({Script.HEBREW, Script.ARABIC})


def script_of(codepoint: int) -> Script:
    """Classify a single code point's script, COMMON for shared characters."""
    for lo, hi, script in _SCRIPT_RANGES:
        if lo <= codepoint <= hi:
            return script
    return Script.COMMON


@dataclass(frozen=True)
class TextRun:
    """A homogeneous-script slice of text with its resolved direction."""

    text: str
    script: Script
    direction: Direction


def _dominant_script(text: str) -> Script:
    """The most-frequent non-COMMON script in `text` (COMMON if none)."""
    counts: dict[Script, int] = {}
    for ch in text:
        s = script_of(ord(ch))
        if s is Script.COMMON:
            continue
        counts[s] = counts.get(s, 0) + 1
    if not counts:
        return Script.COMMON
    return max(counts, key=counts.get)


def classify_run(text: str) -> TextRun:
    """Classify a whole run: its dominant script and paragraph direction.

    A run is RTL if it contains ANY strong RTL character (a Hebrew/Arabic line
    is an RTL paragraph even when it embeds Latin tech proper-nouns).
    """
    has_rtl = any(script_of(ord(ch)) in _RTL_SCRIPTS for ch in text)
    script = _dominant_script(text)
    if has_rtl and script not in _RTL_SCRIPTS:
        # mixed line whose majority is Latin but contains Hebrew/Arabic
        for ch in text:
            s = script_of(ord(ch))
            if s in _RTL_SCRIPTS:
                script = s
                break
    direction = Direction.RTL if has_rtl else Direction.LTR
    return TextRun(text=text, script=script, direction=direction)


def segment_by_script(text: str) -> list[TextRun]:
    """Split a mixed-script run into contiguous same-script segments.

    COMMON characters (spaces, digits, punctuation) attach to the preceding
    segment so neutrals never spawn a segment of their own. Each segment's
    direction is resolved from its own script.
    """
    if not text:
        return []
    segments: list[TextRun] = []
    cur_chars: list[str] = []
    cur_script: Script | None = None

    for ch in text:
        s = script_of(ord(ch))
        if s is Script.COMMON:
            # attach neutrals to the current segment (or start one if leading)
            cur_chars.append(ch)
            if cur_script is None:
                cur_script = Script.COMMON
            continue
        if cur_script is None or s == cur_script or cur_script is Script.COMMON:
            cur_chars.append(ch)
            cur_script = s
        else:
            segments.append(_finish_segment(cur_chars, cur_script))
            cur_chars = [ch]
            cur_script = s

    if cur_chars:
        segments.append(_finish_segment(cur_chars, cur_script or Script.COMMON))
    return segments


def _finish_segment(chars: list[str], script: Script) -> TextRun:
    text = "".join(chars)
    direction = Direction.RTL if script in _RTL_SCRIPTS else Direction.LTR
    return TextRun(text=text, script=script, direction=direction)


# ── Embedded-font reuse + glyph fallback (the FontResolver) ──

# Which bundled Noto family covers a given script for fallback.
_SCRIPT_TO_BUNDLED: dict[Script, BundledFont] = {
    Script.LATIN: BundledFont.LATIN,
    Script.CYRILLIC: BundledFont.LATIN,
    Script.GREEK: BundledFont.LATIN,
    Script.COMMON: BundledFont.LATIN,
    Script.HEBREW: BundledFont.HEBREW,
    Script.ARABIC: BundledFont.HEBREW,  # Noto Sans Hebrew; Arabic POC-out-of-scope
    Script.CJK: BundledFont.CJK,
}


def _looks_bold(font_name: str) -> bool:
    lower = font_name.lower()
    return any(kw in lower for kw in ("bold", "semibold", "heavy", "black"))


@dataclass(frozen=True)
class ResolvedFont:
    """The font chosen to render a run, plus its direction and provenance."""

    font: "fitz.Font"
    direction: Direction
    script: Script
    fallback_used: bool


class FontResolver:
    """Resolves a glyph-complete `fitz.Font` for each text run.

    Strategy (ADR-0001): try the font already embedded in the source PDF (it
    matches the resume's typeface and covers its language). If that font cannot
    cover every code point in the run — common for subsetted CID embeds, whose
    unicode cmap is stripped — fall back to the bundled Noto font for the run's
    script. Fonts are cached per xref and per bundled family.
    """

    def __init__(self, doc: "fitz.Document", *, force_noto: bool = False):
        self._doc = doc
        self._force_noto = force_noto
        self._embedded_by_name: dict[str, fitz.Font] | None = None
        self._embedded_cache: dict[int, fitz.Font | None] = {}
        self._bundled_cache: dict[tuple[BundledFont, bool], fitz.Font] = {}

    # -- embedded font lookup ------------------------------------------------

    def _font_index(self) -> dict[str, fitz.Font]:
        """Lazily build a {base font name -> extracted fitz.Font} index across
        all pages of the source document."""
        if self._embedded_by_name is not None:
            return self._embedded_by_name
        index: dict[str, fitz.Font] = {}
        for page in self._doc:
            for entry in page.get_fonts(full=True):
                xref = entry[0]
                basename = entry[3] or ""
                refname = entry[4] or ""
                font = self._extract(xref)
                if font is None:
                    continue
                for key in (basename, basename.split("+")[-1], refname):
                    if key and key not in index:
                        index[key] = font
        self._embedded_by_name = index
        return index

    def _extract(self, xref: int) -> fitz.Font | None:
        if xref in self._embedded_cache:
            return self._embedded_cache[xref]
        font: fitz.Font | None = None
        try:
            _, _, _, buffer = self._doc.extract_font(xref)
            if buffer:
                font = fitz.Font(fontbuffer=buffer)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Embedded font xref=%s not extractable: %s", xref, exc)
            font = None
        self._embedded_cache[xref] = font
        return font

    # -- bundled (Noto) fallback --------------------------------------------

    def _bundled(self, script: Script, bold: bool) -> fitz.Font:
        family = _SCRIPT_TO_BUNDLED.get(script, BundledFont.LATIN)
        key = (family, bold)
        if key not in self._bundled_cache:
            try:
                path = bundled_font_path(family, bold=bold)
            except FileNotFoundError as exc:
                # Not all families ship with the skill (CJK is 8 MB per face).
                # Degrade to Latin Noto instead of crashing; glyphs for the
                # missing script will render as .notdef boxes.
                logger.warning("%s; falling back to Latin Noto", exc)
                if family is BundledFont.LATIN:
                    raise
                self._bundled_cache[key] = self._bundled(Script.LATIN, bold)
                return self._bundled_cache[key]
            self._bundled_cache[key] = fitz.Font(fontfile=path)
        return self._bundled_cache[key]

    # -- public API ----------------------------------------------------------

    @staticmethod
    def _covers(font: fitz.Font, text: str) -> bool:
        """True if `font` has a glyph for every non-space code point in text."""
        for ch in text:
            if ch.isspace():
                continue
            if not font.has_glyph(ord(ch)):
                return False
        return True

    def resolve(self, text: str, font_name: str) -> ResolvedFont:
        """Resolve a glyph-complete font for `text`, preferring the embedded
        font named `font_name`, else the bundled Noto for the run's script."""
        run = classify_run(text)
        bold = _looks_bold(font_name)

        # Kill-switch (CV_ASSISTANT_FORCE_NOTO=1): skip embedded-font reuse and
        # render everything with the bundled Noto fonts. Robust (never blank)
        # at the cost of not matching the original typeface — flip this if
        # embedded-font extraction ever misbehaves.
        if not self._force_noto:
            embedded = self._font_index().get(font_name)
            if embedded is None:
                embedded = self._font_index().get(font_name.split("+")[-1])

            if embedded is not None and self._covers(embedded, text):
                return ResolvedFont(
                    font=embedded,
                    direction=run.direction,
                    script=run.script,
                    fallback_used=False,
                )

        fallback = self._bundled(run.script, bold)
        return ResolvedFont(
            font=fallback,
            direction=run.direction,
            script=run.script,
            fallback_used=True,
        )
