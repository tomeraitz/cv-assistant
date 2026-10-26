"""Print every text span of a PDF page so a coordinate map can be built.

Usage: ``python lib/inspect_template.py <pdf> [--page 0] [--json]``

Text mode: one line per span ``y0 y1 x0 x1 size font color text`` sorted by
y0 then x0. ``--json``: a list of dicts with keys y0, y1, x0, x1, size, font,
color (#RRGGBB), text.

Exit codes: 0 success; 2 PDF missing or page out of range.
"""

import argparse
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fitz  # noqa: E402

from lib.pdf_utils import get_all_spans  # noqa: E402

logger = logging.getLogger(__name__)


def span_rows(page) -> list[dict]:
    rows = []
    for s in get_all_spans(page):
        x0, y0, x1, y1 = s["bbox"]
        rows.append({
            "y0": round(y0, 1), "y1": round(y1, 1),
            "x0": round(x0, 1), "x1": round(x1, 1),
            "size": round(s["size"], 1),
            "font": s["font"],
            "color": f"#{s['color']:06x}",
            "text": s["text"],
        })
    rows.sort(key=lambda r: (r["y0"], r["x0"]))
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pdf")
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.pdf):
        logger.error("PDF not found: %s", args.pdf)
        return 2
    doc = fitz.open(args.pdf)
    if not 0 <= args.page < doc.page_count:
        logger.error("Page %d out of range (document has %d pages)", args.page, doc.page_count)
        return 2
    page = doc[args.page]
    rows = span_rows(page)

    if args.as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        print(f"# {args.pdf} page {args.page} size={page.rect.width:.0f}x{page.rect.height:.0f} spans={len(rows)}")
        print("y0\ty1\tx0\tx1\tsize\tfont\tcolor\ttext")
        for r in rows:
            print(f"{r['y0']}\t{r['y1']}\t{r['x0']}\t{r['x1']}\t{r['size']}\t{r['font']}\t{r['color']}\t{r['text']}")
    doc.close()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
