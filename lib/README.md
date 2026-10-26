# lib/ — PDF tooling (PyMuPDF)

Run every script from the project root. Requires `pip install pymupdf`. Set `CV_ASSISTANT_FORCE_NOTO=1` to render all inserted text with the bundled Noto fonts (`assets/fonts/`) instead of reusing the template's embedded fonts.

| Script | Purpose | Usage | Exit codes |
|---|---|---|---|
| `inspect_template.py` | List every text span of a page (`y0 y1 x0 x1 size font color text`, sorted by y0 then x0) to build `template-coords.json` | `python lib/inspect_template.py <pdf> [--page 0] [--json]` | 0 ok; 2 PDF missing / page out of range |
| `apply_pdf_changes.py` | Apply section replacements + single find/replace to the template, compress, verify keywords, print report | `python lib/apply_pdf_changes.py <changes.json>` | 0 ok; 2 template/coords/changes.json missing or any section matched 0 spans (nothing written) |
| `compress_pdf.py` | JPEG-recompress images, share duplicate font streams, strip metadata, subset fonts | `python lib/compress_pdf.py <in> [<out>] [--quality 80]` (no `<out>` → replace `<in>` in place) | 0 ok; 2 input missing |
| `pdf_utils.py`, `fonts.py`, `bidi.py` | Library: span extraction, redact+insert via `replace_section()`, per-script font resolution (embedded font → Noto fallback), RTL reordering | imported by the scripts | — |

## profile/template-coords.json
```json
{
  "template": "profile/Full Name CV.pdf",
  "page": 0,
  "sections": {
    "profile": {"description": "Summary paragraph under the name", "y_range": [163, 310], "x_min": 40, "x_max": 375, "size_range": [9, 12], "extend_y": 10, "pad_x": 0, "min_fs": 8.0, "bullets": false, "original_chars": 540, "original_text": "..."},
    "exp_1_bullets": {"description": "Bullets of most recent role", "y_range": [376, 480], "x_min": 43, "x_max": 375, "size_range": [8, 11], "extend_y": 10, "pad_x": 0, "min_fs": 7.5, "bullets": true, "original_chars": 400, "original_text": "line1\nline2"}
  }
}
```
Section keys are free-form labels; parameters are exactly the `replace_section()` kwargs in pdf_utils (`y_range, x_min, x_max, size_range, extend_y, pad_x, min_fs, bullets`). Optional extras: `line_gap` / `item_gap` (leading ratio and extra points between bullets; by default measured from the replaced spans so inserted text keeps the template's spacing), `justify: true` (stretch paragraph lines to the section width, for justified summaries), and `runs` + `text_x` + `baseline` (render one styled line of `{text, font, size, color}` runs instead of `new_text`, e.g. a `date | Title, Company` header where the company is coloured). `original_chars` = character count of the current text in that region (bullets joined with `\n`); `original_text` is the current text. Replacement text should stay within ±10% of `original_chars` to keep font size.

## applications/<slug>/changes.json
```json
{
  "template": "profile/Full Name CV.pdf",
  "coords": "profile/template-coords.json",
  "output": "applications/acme-ai-engineer/Full Name CV.pdf",
  "changes": [{"section": "profile", "new_text": "..."}],
  "single_replacements": [{"find": "Builder,", "replace": "Founder & Engineer,", "label": "title_fix"}],
  "verify_keywords": ["RAG", "LangGraph"]
}
```
`changes[].section` must be a key in coords `sections`; optional per-change overrides of any section parameter are allowed (same key names). `single_replacements` = exact-text find/replace on the page (redact found rect, re-insert replacement in same font/color at adaptive size within the rect extended right to the next span or page margin). A single replacement may instead carry `runs` (list of `{text, font, size, color}`) plus `redact_to` (x): the whole line from the found text to `redact_to` is redacted and re-rendered as one styled line — use this for role headers that mix fonts and colours (date, pipe, title, teal company name), see `lib/apply_pdf_changes.py`. `apply_pdf_changes.py <changes.json>` writes the output PDF, compresses it in place, verifies keywords, prints a report and exits 0; exit 2 if any section matched 0 spans or template/coords missing.
