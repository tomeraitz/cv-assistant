"""Apply a changes.json to a coordinate-mapped PDF template.

Usage: ``python lib/apply_pdf_changes.py <changes.json>`` (run from the project root)

changes.json:
    template            path to the master PDF (default: coords["template"])
    coords              path to template-coords.json (section parameter map)
    output              path of the PDF to write
    changes[]           {"section": <coords key>, "new_text": "...", <param overrides>}
    single_replacements[] {"find": "...", "replace": "...", "label": "..."}
    verify_keywords[]   strings that must appear in the output text

Exit codes: 0 success; 2 template/coords missing or any section matched 0 spans.
"""

import json
import logging
import os
import re
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz  # noqa: E402

from lib.compress_pdf import compress_pdf  # noqa: E402
from lib.fonts import FontResolver  # noqa: E402
from lib.pdf_utils import (  # noqa: E402
    c2rgb,
    get_all_spans,
    insert_runs_adaptive,
    insert_runs_line,
    redact_area,
    replace_section,
)

logger = logging.getLogger(__name__)

# Keys of a coords section (or a change) that are forwarded to replace_section().
# line_gap/item_gap/justify tune leading; runs/text_x/baseline render a styled
# single line (see pdf_utils.insert_runs_line) instead of new_text.
SECTION_PARAMS = ("y_range", "x_min", "x_max", "size_range", "extend_y", "pad_x", "min_fs", "bullets",
                  "line_gap", "item_gap", "justify", "runs", "text_x", "baseline")


def _section_kwargs(section: dict, change: dict) -> dict:
    kwargs = {k: section[k] for k in SECTION_PARAMS if k in section}
    kwargs.update({k: change[k] for k in SECTION_PARAMS if k in change})
    for key in ("y_range", "size_range"):
        if key in kwargs:
            kwargs[key] = tuple(kwargs[key])
    return kwargs


def _overlapping_span(spans, rect: fitz.Rect):
    """The span whose bbox overlaps `rect` the most (None if no overlap)."""
    best, best_area = None, 0.0
    for s in spans:
        inter = fitz.Rect(s["bbox"]) & rect
        area = inter.get_area() if not inter.is_empty else 0.0
        if area > best_area:
            best, best_area = s, area
    return best


def _insert_rect_for(rect: fitz.Rect, spans, page_rect: fitz.Rect) -> fitz.Rect:
    """Found rect extended right up to the next span on the same baseline."""
    x1 = page_rect.x1 - 20
    for s in spans:
        sx0, sy0 = s["bbox"][0], s["bbox"][1]
        if sx0 > rect.x1 + 0.5 and abs(sy0 - rect.y0) < 2:
            x1 = min(x1, sx0 - 2)
    return fitz.Rect(rect.x0, rect.y0, max(x1, rect.x1), rect.y1)


def _line_rect(rect: fitz.Rect, spans, x_to: float) -> fitz.Rect:
    """Rect covering every span sharing the baseline of `rect`, from rect.x0 to x_to."""
    y0, y1 = rect.y0, rect.y1
    for s in spans:
        sx0, sy0, _, sy1 = s["bbox"]
        if rect.x0 - 1 <= sx0 <= x_to and sy0 < rect.y1 and sy1 > rect.y0:
            y0, y1 = min(y0, sy0), max(y1, sy1)
    return fitz.Rect(rect.x0 - 1, y0, x_to, y1)


def apply_single_replacement(page, spans, resolver, item: dict):
    """Exact-text find/replace on the page. Returns True if the text was found.

    Optional keys: ``runs`` (styled runs, see pdf_utils.insert_runs_line) +
    ``redact_to`` (x) replace the whole line from the found text up to
    ``redact_to`` with one styled line (mixed fonts/colours, e.g. a role header).
    """
    find, replace = item["find"], item.get("replace", "")
    label = item.get("label", find)
    hits = page.search_for(find)
    if not hits:
        logger.warning("[%s] MISS: text not found: %r", label, find)
        return False
    rect = hits[0]
    span = _overlapping_span(spans, rect) or {"font": "helv", "size": 10.0, "color": 0,
                                               "origin": (rect.x0, rect.y1 - 2)}
    if item.get("runs"):
        x_to = float(item.get("redact_to", page.rect.x1 - 20))
        line = _line_rect(rect, spans, x_to)
        redact_area(page, [line])
        end_x = insert_runs_line(page, rect.x0, span["origin"][1], item["runs"], resolver,
                                 default_font=span["font"], default_size=span["size"],
                                 default_color=c2rgb(span["color"]))
        logger.info("[%s] OK runs (end_x=%.1f, redact_to=%.1f) %r -> styled line", label, end_x, x_to, find)
        return True
    insert_rect = _insert_rect_for(rect, spans, page.rect)
    redact_area(page, [rect])
    fs = span["size"]
    used_fs, fits = insert_runs_adaptive(
        page, insert_rect, replace, resolver, span["font"], c2rgb(span["color"]),
        fs, min_fs=max(6.0, fs - 3.0),
    )
    logger.info("[%s] OK (fs=%.1f, fits=%s) %r -> %r", label, used_fs, fits, find, replace)
    return True


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_keywords(pdf_path: str, keywords) -> tuple[list, list]:
    doc = fitz.open(pdf_path)
    text = _normalize(" ".join(page.get_text() for page in doc))
    doc.close()
    found = [k for k in keywords if _normalize(k) in text]
    missing = [k for k in keywords if k not in found]
    return found, missing


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        logger.error("Usage: python lib/apply_pdf_changes.py <changes.json>")
        return 2
    if not os.path.isfile(argv[0]):
        logger.error("changes.json not found: %s", argv[0])
        return 2
    with open(argv[0], encoding="utf-8") as fh:
        changes = json.load(fh)

    coords_path = changes.get("coords")
    if not coords_path or not os.path.isfile(coords_path):
        logger.error("Coords file missing: %s", coords_path)
        return 2
    with open(coords_path, encoding="utf-8") as fh:
        coords = json.load(fh)

    template = changes.get("template") or coords.get("template")
    if not template or not os.path.isfile(template):
        logger.error("Template PDF missing: %s", template)
        return 2
    output = changes.get("output")
    if not output:
        logger.error("changes.json has no 'output' path")
        return 2

    sections = coords.get("sections", {})
    page_index = int(changes.get("page", coords.get("page", 0)))

    doc = fitz.open(template)
    page = doc[page_index]
    resolver = FontResolver(doc, force_noto=os.environ.get("CV_ASSISTANT_FORCE_NOTO") == "1")
    all_spans = get_all_spans(page)

    report = []
    section_miss = False
    for change in changes.get("changes", []):
        label = change["section"]
        section = sections.get(label)
        if section is None:
            logger.warning("[%s] MISS: section not in coords", label)
            report.append(f"MISS {label} (not in coords)")
            section_miss = True
            continue
        kwargs = _section_kwargs(section, change)
        if "y_range" not in kwargs:
            logger.warning("[%s] MISS: section has no y_range", label)
            report.append(f"MISS {label} (no y_range)")
            section_miss = True
            continue
        result = replace_section(page, all_spans, new_text=change["new_text"], label=label,
                                 resolver=resolver, **kwargs)
        if result is None:
            report.append(f"MISS {label}")
            section_miss = True
        else:
            used_fs, rc = result
            # insert_runs_adaptive returns a bool; insert_bulleted_runs returns remaining height (-1 = overflow)
            fits = rc is True or (not isinstance(rc, bool) and rc >= 0)
            report.append(f"OK {label} fs={used_fs:.1f} fits={fits} chars={len(change['new_text'])}")

    for item in changes.get("single_replacements", []):
        ok = apply_single_replacement(page, all_spans, resolver, item)
        label = item.get("label", item["find"])
        report.append(f"{'OK' if ok else 'MISS'} single:{label}")

    print("\n=== apply_pdf_changes report ===")
    for line in report:
        print(line)
    if section_miss:
        print("ABORTED: a section matched 0 spans; nothing written")
        doc.close()
        return 2

    out_dir = os.path.dirname(os.path.abspath(output))
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=out_dir)
    os.close(fd)
    try:
        doc.save(tmp_path, garbage=4, deflate=True)
        doc.close()
        compress_pdf(tmp_path, output)
    finally:
        # OneDrive / antivirus may hold a fresh file briefly on Windows; retry before giving up.
        for attempt in range(5):
            if not os.path.exists(tmp_path):
                break
            try:
                os.remove(tmp_path)
            except PermissionError:
                if attempt == 4:
                    logger.warning("could not remove temp file %s", tmp_path)
                else:
                    time.sleep(0.3)

    found, missing = verify_keywords(output, changes.get("verify_keywords", []))
    print(f"keywords found: {found}")
    print(f"keywords missing: {missing}")
    print(f"output: {output}")
    print(f"size: {os.path.getsize(output) / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
