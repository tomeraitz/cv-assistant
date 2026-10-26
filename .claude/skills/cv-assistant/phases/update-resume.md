# Phase B — Update the master resume

Edits `profile/history.md` and regenerates `profile/<Name> CV.pdf` (and `profile/template-coords.json`, `profile/profile.json`).
Read `reference/history-format.md`, `reference/interview-questions.md`, `reference/truthfulness-policy.md` first. Read `profile/history.md`, `profile/profile.json`, `profile/template-coords.json`.

## Step 0 — Pick the sub-flow

Infer from the request; if unclear, ask once (AskUserQuestion, four options):

| Sub-flow | Changes in history.md | Changes in the resume | Interview topics |
|---|---|---|---|
| **B1 Add a position** ("I started a new job") | new `### <Company> - <Role> (<start> – <end>)` block at the top of `## Career Journey`; previous role gets an end date | experience section: newest role becomes `exp_1_bullets`, older ones shift down or the oldest is dropped | company, title, dates, team/scope, stack, 2–3 measurable results, what to emphasize |
| **B2 Update an existing position** ("I got promoted", "new results") | edit that block | that role's bullets | which role; what is new (title, results, stack) |
| **B3 Remove a position** | delete the block | that role's bullets removed; later roles shift | which role; confirm |
| **B4 Change target job title** ("apply as Data Engineer now") | `## Looking For`; `profile.json.target_titles` | summary/headline section; skills to foreground | new title(s); keep or drop old ones; skills to foreground |

## Step 1 — Interview

One topic per turn. Ask for numbers; never assume them. Stop when the sub-flow's topics are covered.

## Step 2 — Show the diff

1. `history.md` before/after for the affected blocks (quoted old block, quoted new block).
2. Proposed resume text, per affected section from `template-coords.json`:
   ```
   ## <label>  (original N chars → replacement M chars, limit ±10% of N)
   Original:    <original_text>
   Replacement: <new text>
   ```
   Role headers/dates that change outside a mapped section go into a `Single Replacements` list (`find → replace`).
3. Replacement exceeding +10% of `original_chars` → say so and offer three options: shorten the text, drop an older bullet, or stop (the user edits the template PDF manually; nothing is written).
4. `profile.json` changes (B4: `target_titles`; always: `updated_at`).

## Step 3 — Approval

AskUserQuestion: **approve** / **edit** / **cancel**. Edit → apply the user's changes, show the diff again. Cancel or no explicit approval → write nothing and end.

## Step 4 — Write on approval

1. Write `profile/history.md` (full file).
2. Write the approved mappings to `profile/update-rewrite.md` in the `## Section:` / `### Original` / `### Replacement` / `## Single Replacements` format (temporary input for pdf-writer; `applications/` is not used in this phase).
3. Backup: rename `profile/<Name> CV.pdf` → `profile/<Name> CV.<YYYY-MM-DD>.pdf` (today's date). The backup is the template input; pdf-writer writes the new `profile/<Name> CV.pdf`. Keep only the newest backup: delete older `profile/<Name> CV.*.pdf` after step 5 passes.
4. Agent tool, `subagent_type: pdf-writer`:
   ```
   Apply approved text changes to the master resume template.
   rewrite_path: profile/update-rewrite.md
   ats_path: none (no ATS report; use only rewrite_path)
   coords_path: profile/template-coords.json
   template_pdf_path: profile/<Name> CV.<YYYY-MM-DD>.pdf
   output_pdf_path: profile/<Name> CV.pdf
   changes_json_path: profile/update-changes.json
   Write changes.json ({template, coords, output, changes[{section,new_text}], single_replacements[{find,replace,label}], verify_keywords: []}), then run: python lib/apply_pdf_changes.py profile/update-changes.json  and report its full output and exit code. Read only the files listed.
   ```
   Exit code 2 → show the report, fix labels/overrides in `profile/update-changes.json`, re-run the command yourself. On failure restore: copy the backup back to `profile/<Name> CV.pdf`.
5. Verify: `python -c "import fitz;print(fitz.open(r'profile/<Name> CV.pdf')[0].get_text())"` contains the new text and no old text for the changed sections.
6. Update `profile/template-coords.json`: for every changed section set `original_text` to the new text and `original_chars` to its length. Do not change coordinates.
7. Update `profile/profile.json`: `updated_at` = today; B4 also `target_titles`.
8. Delete `profile/update-rewrite.md` and `profile/update-changes.json`.

## End

Saved: `profile/history.md`, `profile/<Name> CV.pdf` (backup `profile/<Name> CV.<YYYY-MM-DD>.pdf`), `profile/template-coords.json`, `profile/profile.json`.
Related line: "I can now fit this updated resume to a job — open a new conversation and paste the posting." Then stop (SKILL.md Step 3).
