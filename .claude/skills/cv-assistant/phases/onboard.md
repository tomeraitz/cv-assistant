# Phase A — Onboard (no profile yet)

Creates `profile/history.md`, `profile/profile.json`, `profile/<Name> CV.pdf`, `profile/template-coords.json`.
Read `reference/history-format.md`, `reference/interview-questions.md`, `reference/truthfulness-policy.md` first.

A PDF resume is required: it becomes the coordinate-mapped template that every later phase edits. Do not finish this phase without one.

## Step 1 — Get the existing resume

Ask the user to attach or give the path to their current resume.
- `.pdf` → used for content and as the template.
- `.docx` / `.md` / pasted text → content only; still ask for a PDF before step 5. If the user has none, say the phase cannot finish without a PDF resume and stop after writing nothing (or wait for one).

## Step 2 — Draft `history.md`

Read the resume (PDF text: `python -c "import fitz;print(fitz.open(r'<path>')[0].get_text())"`, add `[1]`… for more pages).
Fill `templates/history.template.md` per `reference/history-format.md`: one `### <Company> - <Role> (<start> – <end>)` block per role, Education, Projects, Skills, Languages, Looking For. Copy facts only; leave `_missing_` markers where the resume has no data (numbers, team size, stack).

## Step 3 — Interview (≤ 5 turns, one topic per turn)

Use `reference/interview-questions.md`. Order: per role → scope and team size, stack, 2–3 measurable results; then education; then target titles; then languages. Ask for numbers; never estimate them. Skip topics already complete.

## Step 4 — Approve the draft

Show the full draft `history.md`. Iterate on the user's corrections until they say it is approved. Nothing is written before that.

## Step 5 — Save the profile

1. Create `profile/`. Write `profile/history.md`.
2. Write `profile/profile.json`:
   ```json
   {"name": "<Full Name>", "target_titles": ["<title>", "..."], "language": "en", "updated_at": "<YYYY-MM-DD>"}
   ```
3. Copy the PDF to `profile/<Name> CV.pdf`, where `<Name>` is `profile.json.name` as written (e.g. `profile/Full Name CV.pdf`); Bash copy, do not alter the file.

## Step 6 — Build `profile/template-coords.json`

1. Run `python lib/inspect_template.py profile/<Name> CV.pdf` (add `--json` for machine-readable output). Each line is one span: `y0 y1 x0 x1 size font color text`.
2. Group spans into editable sections. Typical sections: `profile` (summary paragraph), `exp_1_bullets`, `exp_2_bullets`, … (bullets of each role, most recent first), `skills_1`, `skills_2`, … (skill blocks). Skip headers, name, contact line and dates — they are not rewritten.
3. For each section compute:
   - `y_range`: `[floor(min y0) − 2, ceil(max y1) + 2]` of its spans; `x_min` / `x_max`: `floor(min x0) − 2` / `ceil(max x1) + 2`. The region from `y_range[0]` down is redacted, so `y_range[0]` must be BELOW the bottom (`y1`) of any bold heading above the section (e.g. "Skills", "AI/ML:") or the heading is erased;
   - `size_range`: tight around the body size (`[size − 0.5, size + 0.5]`) so bold headings and titles in a different size never match;
   - `min_fs`: `size − 1.5`; `extend_y`: 10; `pad_x`: 0; `bullets`: true when the spans are bullet lines;
   - `original_text`: for bullet sections one LOGICAL bullet per line — merge wrapped visual lines into their bullet (a bullet usually ends with `.`), joined with `\n`; for paragraphs and skill lists join all visual lines with a space (no `\n`, the text re-wraps on insert). `original_chars`: `len(original_text)`.
   - For a bullet section, set `x_min` ≈ 15 pt left of the text so the redaction also covers the template's vector bullet dots; the script redraws dots.
4. Write the file:
   ```json
   {
     "template": "profile/<Name> CV.pdf",
     "page": 0,
     "sections": {
       "profile": {"description": "Summary paragraph under the name", "y_range": [163, 310], "x_min": 40, "x_max": 375, "size_range": [9, 12], "extend_y": 10, "pad_x": 0, "min_fs": 8.0, "bullets": false, "original_chars": 540, "original_text": "..."},
       "exp_1_bullets": {"description": "Bullets of most recent role", "y_range": [376, 480], "x_min": 43, "x_max": 375, "size_range": [8, 11], "extend_y": 10, "pad_x": 0, "min_fs": 7.5, "bullets": true, "original_chars": 400, "original_text": "line1\nline2"}
     }
   }
   ```
5. Show the user a table `section | description | chars | first 60 chars of original_text` and ask whether the grouping matches their resume. Fix and rewrite on feedback.

## End

Saved: `profile/history.md`, `profile/profile.json`, `profile/<Name> CV.pdf`, `profile/template-coords.json`.
Related line → Phase C (fit to a job). Then stop (SKILL.md Step 3).
