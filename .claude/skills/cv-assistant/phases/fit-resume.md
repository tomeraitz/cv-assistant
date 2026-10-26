# Phase C — Fit resume to a job

Inputs: `profile/history.md`, `profile/<Name> CV.pdf`, `profile/template-coords.json`, `profile/profile.json` (`name`).
Output folder: `applications/<slug>/`. Read `reference/truthfulness-policy.md` before step 3.

## Step 1 — Get the job posting

Resolve the input in this order:
1. URL and browser tools are available (any browser MCP tools or a Cowork browser — never require a specific tool): open the page in the user's browser and extract the fields in `reference/jd-extraction.md`. Login wall or CAPTCHA → pause, ask the user to handle it in the browser, then continue.
2. URL, no browser tools: mention once that the Claude in Chrome extension lets the skill read postings from the browser, then WebFetch the URL. If WebFetch fails or returns a login page (common for LinkedIn/Indeed), ask the user to paste the posting text.
3. Pasted text: use it directly. If company or title cannot be inferred from the text, ask for them (one question).

## Step 2 — Create the application folder and `jd.md`

1. Build the slug per `reference/folder-naming.md` (`<company>-<job-title>`; collision → `-2`, `-3`).
2. Create `applications/<slug>/`.
3. Write `applications/<slug>/jd.md` before anything else:

```markdown
# <Title> at <Company>

- Source: <URL or "pasted text">
- Captured: <YYYY-MM-DD>
- Location: <location or "not stated">
- Seniority: <seniority or "not stated">

## Must-have
- ...

## Nice-to-have
- ...

## Keywords
<comma-separated>

## Full text
<complete posting text, unedited>
```

## Step 3 — Workers 1 → 2 → 3 (sequential, each via the Agent tool)

Replace `<slug>` with the folder name. Workers never ask the user anything; if a worker returns a question, answer it yourself from the files or ask the user and re-run.

### Worker 1 — `hiring-manager-reviewer`
Agent tool, `subagent_type: hiring-manager-reviewer`, prompt:
```
Evaluate how well this candidate fits the job.
jd_path: applications/<slug>/jd.md
history_path: profile/history.md
template_pdf_path: profile/<Name> CV.pdf
output_path: applications/<slug>/match-report.md
Write match-report.md with: ## Match Score: N/100 (skills 40 / experience 30 / keywords 30), ## Missing Keywords (top 5), ## Strengths, ## Gaps. Read only the files listed. Return a summary of at most 10 lines.
```

### Worker 2 — `rewrite-resume`
```
Rewrite resume sections to close the gaps in the match report, using only facts from history.md.
match_report_path: applications/<slug>/match-report.md
history_path: profile/history.md
template_pdf_path: profile/<Name> CV.pdf
coords_path: profile/template-coords.json
output_path: applications/<slug>/rewrite.md
Write rewrite.md with one "## Section: <label>" block per changed section (label = a key in coords sections), each with "### Original" (text, N chars) and "### Replacement" (text, N chars, within ±10% of original_chars); then "## Single Replacements" (find → replace list) and "## Keywords Not Added" (no evidence in history). Use X-Y-Z bullets. Read only the files listed. Return a summary of at most 10 lines.
```

### Worker 3 — `application-tracking-system`
```
Scan the proposed resume text as an ATS parser would.
rewrite_path: applications/<slug>/rewrite.md
template_pdf_path: profile/<Name> CV.pdf
coords_path: profile/template-coords.json
output_path: applications/<slug>/ats-report.md
Write ats-report.md with: ## ATS Score: N/100, ## Issues, ## Additional Changes (same "## Section: <label>" / ### Original / ### Replacement format, labels from coords sections). Read only the files listed. Return a summary of at most 10 lines.
```

## APPROVAL GATE (skill, in the main conversation)

Nothing is written to a PDF before this gate passes.

1. Read `rewrite.md` and `ats-report.md`. Merge per section: an ATS change for the same section label replaces the rewrite change (ATS wins on conflict). Append ATS-only sections. Keep `## Single Replacements` and `## Keywords Not Added`.
2. Show the user, per section:
   ```
   ## <label>  (original N chars → replacement M chars, limit ±10% of N)
   Original:    <text>
   Replacement: <text>
   ```
   then the single replacements (`find → replace`), then the keywords not added, then the match score and ATS score.
3. AskUserQuestion with options: **approve** / **edit** / **regenerate**.
   - approve → continue to step 4.
   - edit → take the user's edits, apply them to `applications/<slug>/rewrite.md` (edit the affected `## Section:` blocks; add sections that came from ATS so rewrite.md is the single approved source), re-check the ±10% char rule and that every claim traces to `history.md`, show the result again, ask again.
   - regenerate → re-run Worker 2 with the user's feedback appended to the prompt, then Worker 3, then show the gate again.
4. If the user edited, note in the Worker 4 prompt that rewrite.md already contains the merged approved changes.

## Step 4 — Worker 4 `pdf-writer` (builds the PDF)

`<Name>` = `profile.json.name` (e.g. `applications/<slug>/Full Name CV.pdf`).
```
Build the tailored PDF from the approved changes.
rewrite_path: applications/<slug>/rewrite.md
ats_path: applications/<slug>/ats-report.md
coords_path: profile/template-coords.json
template_pdf_path: profile/<Name> CV.pdf
output_pdf_path: applications/<slug>/<Name> CV.pdf
changes_json_path: applications/<slug>/changes.json
Write changes.json ({template, coords, output, changes[{section,new_text}], single_replacements[{find,replace,label}], verify_keywords}); merge rewrite + ATS changes, ATS wins on conflict. Then run: python lib/apply_pdf_changes.py applications/<slug>/changes.json  and report its full output and exit code. Read only the files listed.
```
Exit code 2 (section matched 0 spans, or template/coords missing) → show the report to the user; fix the section label or coords override in `changes.json` and re-run `python lib/apply_pdf_changes.py applications/<slug>/changes.json` yourself. Do not continue with a missing PDF.

## Step 5 — Accuracy gate (skill, not a worker)

1. Extract the final PDF text:
   ```
   python -c "import fitz;print(fitz.open(r'applications/<slug>/<Name> CV.pdf')[0].get_text())"
   ```
2. Read `profile/history.md`. For every factual claim in the PDF text (role, company, dates, numbers, technologies, tools, degrees, certifications) find the supporting line in `history.md`.
3. Unsupported claim found:
   - First time: re-run Worker 2 once with the prompt prefixed by `VIOLATIONS TO REMOVE: <list of unsupported claims>`, then Worker 3, the approval gate, Worker 4, and this step again.
   - Second time: keep the PDF, flag the remaining claims to the user as unresolved.
4. Write `applications/<slug>/accuracy-check.md`:
   ```markdown
   # Accuracy check — <Title> at <Company>
   - PDF: applications/<slug>/<Name> CV.pdf
   - Checked: <YYYY-MM-DD>
   - Result: PASS | FLAGGED

   | Claim in PDF | Evidence in history.md | Status |
   |---|---|---|
   | ... | <quoted line or "none"> | supported / unsupported |
   ```

## Final summary (then Step 3 of SKILL.md)

- Match score (from match-report.md), ATS score (from ats-report.md), accuracy result.
- PDF path: `applications/<slug>/<Name> CV.pdf`.
- Saved files: jd.md, match-report.md, rewrite.md, ats-report.md, changes.json, the PDF, accuracy-check.md.
- If the user mentioned experience during this conversation that is not in `history.md`, say: "You mentioned <X> but it is not in your history." and make the Related line point to Phase B.
