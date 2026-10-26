"""
Reusable PDF manipulation utilities for CV creation.
Uses PyMuPDF (fitz) to modify PDF templates via redact + insert.

Insertion is multi-language: each text run is rendered with the font resolved
from the source PDF (Noto fallback per script — see lib/fonts.py) via
``fitz.TextWriter``. RTL runs are bidi-reordered (lib/bidi.py) and right-aligned.
The active pipeline path is ``replace_section`` -> ``insert_runs_adaptive`` /
``insert_bulleted_runs``.
"""

import fitz
import logging

from lib.bidi import get_display
from lib.fonts import Direction, FontResolver, segment_by_script

logger = logging.getLogger(__name__)


# ── Color Utilities ──

def c2rgb(color_int):
    """Convert 0xRRGGBB integer to (r, g, b) float tuple."""
    return (
        (color_int >> 16 & 0xFF) / 255,
        (color_int >> 8 & 0xFF) / 255,
        (color_int & 0xFF) / 255,
    )


# ── Span Extraction ──

def get_all_spans(page):
    """Extract all non-empty text spans from a PDF page with full properties."""
    spans = []
    for bi, block in enumerate(page.get_text("dict")["blocks"]):
        if "lines" not in block:
            continue
        for li, line in enumerate(block["lines"]):
            for si, span in enumerate(line["spans"]):
                if span["text"].strip():
                    font = span["font"]
                    spans.append({
                        "bi": bi, "li": li, "si": si,
                        "text": span["text"],
                        "font": font.split("+")[-1] if "+" in font else font,
                        "size": span["size"],
                        "color": span["color"],
                        "bbox": span["bbox"],
                        "origin": span["origin"],
                    })
    return spans


def find_spans_by_area(spans, y_min, y_max, x_min=0, x_max=9999, size_min=0, size_max=999):
    """Filter spans by bounding box area and font size range."""
    return [
        s for s in spans
        if y_min < s["bbox"][1] < y_max
        and x_min <= s["bbox"][0] <= x_max
        and size_min <= s["size"] <= size_max
    ]


def get_section_bbox(spans):
    """Compute the overall bounding box from a list of spans."""
    if not spans:
        return None
    return (
        min(s["bbox"][0] for s in spans),  # x0
        min(s["bbox"][1] for s in spans),  # y0
        max(s["bbox"][2] for s in spans),  # x1
        max(s["bbox"][3] for s in spans),  # y1
    )


# ── PDF Modification ──

def redact_area(page, rects):
    """Redact a list of fitz.Rect areas with white fill."""
    for r in rects:
        page.add_redact_annot(r, fill=(1, 1, 1))
    page.apply_redactions(graphics=fitz.PDF_REDACT_IMAGE_REMOVE)


# ── Unicode-aware insertion via fitz.TextWriter ──
#
# Replaces the builtin-Helvetica path: each text run is rendered with the font
# resolved from the source PDF (Noto fallback per script), splitting mixed-script
# lines into per-run fonts. RTL runs are bidi-reordered and right-aligned.


class _Token:
    """A whitespace-delimited token tagged with its resolved font + direction."""

    __slots__ = ("text", "font", "direction", "width")

    def __init__(self, text, font, direction, fontsize):
        self.text = text
        self.font = font
        self.direction = direction
        self.width = font.text_length(text, fontsize=fontsize)


def _tokenize(line, resolver, font_name, fontsize):
    """Split a logical line into font-tagged word tokens (script-segmented)."""
    tokens = []
    for segment in segment_by_script(line):
        resolved = resolver.resolve(segment.text, font_name)
        # Keep spaces as their own zero-content separators by splitting on them
        # while preserving word grouping per segment.
        parts = segment.text.split(" ")
        for i, part in enumerate(parts):
            if part:
                tokens.append(_Token(part, resolved.font, resolved.direction, fontsize))
            if i < len(parts) - 1:
                tokens.append(_Token(" ", resolved.font, resolved.direction, fontsize))
    return tokens


def _wrap_tokens(tokens, max_width):
    """Greedy word-wrap tokens into lines that fit max_width. Returns list of
    lines, each a list of tokens (leading/trailing spaces trimmed)."""
    lines = []
    current = []
    width = 0.0
    for tok in tokens:
        if tok.text == " ":
            if current:  # don't start a line with a space
                current.append(tok)
                width += tok.width
            continue
        if current and width + tok.width > max_width:
            # drop trailing space tokens
            while current and current[-1].text == " ":
                current.pop()
            lines.append(current)
            current = [tok]
            width = tok.width
        else:
            current.append(tok)
            width += tok.width
    if current:
        while current and current[-1].text == " ":
            current.pop()
        lines.append(current)
    return lines


def _line_is_rtl(line_tokens):
    return any(t.direction is Direction.RTL for t in line_tokens)


def _line_width(line_tokens):
    return sum(t.width for t in line_tokens)


def _emit_line(tw, line_tokens, x0, x1, baseline_y, fontsize, rtl, justify=False):
    """Append one laid-out line to the TextWriter, applying RTL bidi + right
    alignment. With ``justify`` (LTR only) the slack up to ``x1`` is spread
    evenly over the line's space tokens. Returns nothing; mutates the writer."""
    if not line_tokens:
        return
    line_text = "".join(t.text for t in line_tokens)
    width = _line_width(line_tokens)
    if rtl:
        # bidi-reorder the whole visual line, render right-aligned with the
        # dominant RTL font (Noto Hebrew covers embedded Latin tech tokens too).
        visual = get_display(line_text, base_dir="R")
        font = _dominant_font(line_tokens)
        start_x = x1 - width
        tw.append(fitz.Point(start_x, baseline_y), visual, font=font, fontsize=fontsize)
    else:
        extra = 0.0
        if justify:
            n_spaces = sum(1 for t in line_tokens if t.text == " ")
            slack = (x1 - x0) - width
            # Never stretch a line by more than ~1/3 of its width (last lines
            # and very short lines stay ragged like a word processor would).
            if n_spaces and 0 < slack < (x1 - x0) / 3:
                extra = slack / n_spaces
        x = x0
        for tok in line_tokens:
            tw.append(fitz.Point(x, baseline_y), tok.text, font=tok.font, fontsize=fontsize)
            x += tok.width + (extra if tok.text == " " else 0.0)


def _parse_color(value, default):
    """'#rrggbb' / 0xRRGGBB int / (r,g,b) floats -> (r,g,b) floats."""
    if value is None:
        return default
    if isinstance(value, str):
        v = value.lstrip("#")
        return c2rgb(int(v, 16))
    if isinstance(value, int):
        return c2rgb(value)
    return tuple(value)


def insert_runs_line(page, x0, baseline_y, runs, resolver, default_font="helv",
                     default_size=10.0, default_color=(0.2, 0.2, 0.2)):
    """Render one line made of styled runs, left-to-right from ``x0``.

    Each run: ``{"text": str, "font": <PDF font name>, "size": float,
    "color": "#rrggbb"}``; missing keys inherit the defaults (taken from the
    span being replaced). Used for header-like lines that mix fonts, sizes and
    colours (e.g. ``date | Title, Company``). Returns the x where the line ends.
    """
    x = x0
    writers = []
    for run in runs:
        text = run.get("text", "")
        if not text:
            continue
        font_name = run.get("font", default_font)
        size = float(run.get("size", default_size))
        color = _parse_color(run.get("color"), default_color)
        resolved = resolver.resolve(text, font_name)
        tw = fitz.TextWriter(page.rect, color=color)
        tw.append(fitz.Point(x, baseline_y), text, font=resolved.font, fontsize=size)
        writers.append(tw)
        x += resolved.font.text_length(text, fontsize=size)
    for tw in writers:
        tw.write_text(page)
    return x


def derive_line_metrics(spans, fontsize):
    """Infer (line_gap, item_gap) from the baselines of the spans being
    replaced, so inserted text keeps the template's own leading.

    line_gap: line-height / font-size (ratio). item_gap: extra points between
    bulleted items (the larger baseline step minus the regular one). Falls
    back to (1.15, 2.0) when the spans give no usable signal.
    """
    origins = sorted({round(s["origin"][1], 1) for s in spans})
    deltas = [b - a for a, b in zip(origins, origins[1:]) if b - a > 2.0]
    if not deltas or fontsize <= 0:
        return 1.15, 2.0
    line_h = min(deltas)
    line_gap = max(1.0, min(1.8, line_h / fontsize))
    extras = sorted(d - line_h for d in deltas if d - line_h > 1.5)
    item_gap = extras[len(extras) // 2] if extras else 2.0
    return line_gap, item_gap


def _dominant_font(line_tokens):
    """Pick the font covering the most characters in the line (RTL primary)."""
    best = None
    best_len = -1
    for tok in line_tokens:
        if tok.direction is Direction.RTL and len(tok.text) > best_len:
            best = tok.font
            best_len = len(tok.text)
    if best is not None:
        return best
    return line_tokens[0].font


def _layout_paragraph(line, resolver, font_name, fontsize, rect):
    """Word-wrap one logical paragraph into lines (lists of font-tagged tokens)
    that fit ``rect.width``. Pure measurement — writes nothing — so callers can
    shrink-to-fit before committing the layout.
    """
    tokens = _tokenize(line, resolver, font_name, fontsize)
    return _wrap_tokens(tokens, rect.width)


def insert_runs_adaptive(page, rect, text, resolver, font_name, color,
                         start_fs, min_fs=7.0, line_gap=1.15, justify=False):
    """Insert `text` into `rect` using TextWriter + resolved per-run fonts,
    shrinking the font size until every wrapped line fits the rect height.

    Multi-line input (``\n``) is treated as separate paragraphs. RTL paragraphs
    are bidi-reordered and right-aligned. ``line_gap`` is the line-height /
    font-size ratio; ``justify`` stretches every line but a paragraph's last.
    Returns (used_fontsize, fits) where ``fits`` is True if everything fit
    within the rect.
    """
    paragraphs = text.split("\n")
    fs = start_fs

    while fs >= min_fs:
        all_lines = []  # (line_tokens, rtl, is_last_in_paragraph)
        for para in paragraphs:
            if not para.strip():
                all_lines.append(([], False, True))
                continue
            wrapped = _layout_paragraph(para, resolver, font_name, fs, rect)
            rtl = any(_line_is_rtl(line) for line in wrapped)
            for i, line in enumerate(wrapped):
                all_lines.append((line, rtl, i == len(wrapped) - 1))

        line_height = fs * line_gap
        total_height = line_height * len(all_lines)
        if total_height <= rect.height or fs <= min_fs:
            tw = fitz.TextWriter(page.rect, color=color)
            baseline = rect.y0 + fs  # first baseline
            for line_tokens, rtl, last in all_lines:
                _emit_line(tw, line_tokens, rect.x0, rect.x1, baseline, fs, rtl,
                           justify=justify and not last)
                baseline += line_height
            tw.write_text(page)
            fits = total_height <= rect.height
            return fs, fits
        fs -= 0.5

    return min_fs, False


def insert_bulleted_runs(page, rect, text, resolver, font_name, color,
                         start_fs, min_fs=7.0, bullet_indent=4.0, text_indent=15.0,
                         line_gap=1.15, item_gap=2.0):
    """Bulleted variant of ``insert_runs_adaptive``: each ``\n``-separated item
    becomes a hanging-indent bullet, rendered with resolved per-run fonts and
    RTL-aware. ``line_gap`` / ``item_gap`` control leading and the extra space
    between items. Returns (used_fontsize, remaining_height)."""
    items = [it for it in text.split("\n")]
    bullet_r = 1.8
    line_gap_mult = line_gap

    fs = start_fs
    while fs >= min_fs:
        # Measure: wrap every item; count total lines. Wrapping width is the
        # rect minus the text indent; for RTL the indent is on the right, for
        # LTR on the left — the available text width is the same either way.
        item_lines = []
        item_rtl = []
        for item in items:
            if not item.strip():
                item_lines.append([])
                item_rtl.append(False)
                continue
            text_rect = fitz.Rect(rect.x0, rect.y0, rect.x1 - text_indent, rect.y1)
            wrapped = _layout_paragraph(item, resolver, font_name, fs, text_rect)
            item_lines.append(wrapped)
            item_rtl.append(any(_line_is_rtl(line) for line in wrapped))

        line_height = fs * line_gap_mult
        total = 0.0
        for lines in item_lines:
            total += max(len(lines), 1) * line_height + item_gap
        total -= item_gap

        if total <= rect.height or fs <= min_fs:
            tw = fitz.TextWriter(page.rect, color=color)
            y = rect.y0 + fs
            for lines, rtl in zip(item_lines, item_rtl):
                if not lines:
                    y += line_height + item_gap
                    continue
                if rtl:
                    # RTL: text hugs the right edge inset by text_indent; the
                    # bullet sits in the gap to the right, near rect.x1.
                    text_x0 = rect.x0
                    text_x1 = rect.x1 - text_indent
                    bullet_x = rect.x1 - bullet_indent
                else:
                    text_x0 = rect.x0 + text_indent
                    text_x1 = rect.x1
                    bullet_x = rect.x0 + bullet_indent
                # bullet dot aligned to first line
                page.draw_circle(fitz.Point(bullet_x, y - fs * 0.3), bullet_r,
                                 color=color, fill=color)
                for line_tokens in lines:
                    line_rtl = _line_is_rtl(line_tokens)
                    _emit_line(tw, line_tokens, text_x0, text_x1, y, fs, line_rtl)
                    y += line_height
                y += item_gap
            tw.write_text(page)
            return fs, rect.height - total
        fs -= 0.5
    return min_fs, -1


# ── High-Level Section Replacement ──

def replace_section(page, all_spans, y_range, new_text, label, resolver,
                    x_min=0, x_max=9999, size_range=(0, 999),
                    extend_y=5, pad_x=0, min_fs=7.0, bullets=False,
                    line_gap=None, item_gap=None, justify=False,
                    runs=None, text_x=None, baseline=None):
    """
    Find spans in a y/x/size range, redact them, and insert new_text using the
    FontResolver (embedded-font reuse + Noto fallback, RTL-aware) via TextWriter.

    ``line_gap`` / ``item_gap`` default to the leading measured on the replaced
    spans (see ``derive_line_metrics``). ``justify`` stretches paragraph lines
    to the section width. ``runs`` (list of styled runs, see
    ``insert_runs_line``) renders a single header-like line instead of
    ``new_text``, starting at ``text_x`` (default: section left edge) on
    ``baseline`` (default: first replaced span's baseline).
    Returns (used_fontsize, fits) or None if no spans found.
    """
    spans = find_spans_by_area(
        all_spans, y_range[0], y_range[1],
        x_min=x_min, x_max=x_max,
        size_min=size_range[0], size_max=size_range[1],
    )
    if not spans:
        logger.warning("[%s] MISS: no spans in range", label)
        return None

    bbox = get_section_bbox(spans)
    x0, y0, x1, y1 = bbox

    # Prefer regular (non-bold) font — bold spans are usually section headers
    regular_spans = [s for s in spans if "Bold" not in s["font"] and "bold" not in s["font"].lower()]
    ref_span = regular_spans[0] if regular_spans else spans[0]
    fn = ref_span["font"]
    fs = ref_span["size"]
    co = c2rgb(ref_span["color"])

    # Use x_min if provided and smaller than span bbox
    redact_x0 = min(x0, x_min) if x_min > 0 else x0

    # Redact with small padding
    redact_y0 = min(y0, y_range[0])
    redact_area(page, [fitz.Rect(redact_x0 - 1, redact_y0, x1 + pad_x + 5, y1)])

    if runs:
        # Styled single line (header-like): no wrapping, no shrinking.
        bx = redact_x0 if text_x is None else float(text_x)
        by = ref_span["origin"][1] if baseline is None else float(baseline)
        end_x = insert_runs_line(page, bx, by, runs, resolver,
                                 default_font=fn, default_size=fs, default_color=co)
        fits = end_x <= x1 + pad_x + 5
        logger.info("[%s] OK runs (baseline=%.1f, end_x=%.1f, fits=%s)", label, by, end_x, fits)
        return fs, fits

    auto_gap, auto_item = derive_line_metrics(spans, fs)
    line_gap = auto_gap if line_gap is None else float(line_gap)
    item_gap = auto_item if item_gap is None else float(item_gap)

    # Insert with optional extension
    rect = fitz.Rect(redact_x0, y0, x1 + pad_x, y1 + extend_y)
    if bullets:
        used_fs, rc = insert_bulleted_runs(page, rect, new_text, resolver, fn, co, fs, min_fs=min_fs,
                                           line_gap=line_gap, item_gap=item_gap)
    else:
        rect_text = fitz.Rect(x0, y0, x1 + pad_x, y1 + extend_y)
        used_fs, rc = insert_runs_adaptive(page, rect_text, new_text, resolver, fn, co, fs, min_fs=min_fs,
                                           line_gap=line_gap, justify=justify)
    logger.info("[%s] OK (fs=%.1f, fits=%s, chars=%d, line_gap=%.2f)", label, used_fs, rc, len(new_text), line_gap)
    return used_fs, rc
