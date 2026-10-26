# Phase D — Research a role

Wraps the `cv-researcher` worker. No resume is changed in this phase.

## Step 1 — Inputs

- `title` (required): ask if not given.
- `company` (optional).
- Posting: if the user gave a URL or text, capture it as `jd.md` using Phase C step 1–2 rules (`reference/jd-extraction.md`, `reference/folder-naming.md`). Otherwise no `jd.md`.

Output path:
- company known → `applications/<company>-<job-title>/research.md` (create the folder per `reference/folder-naming.md`; reuse an existing folder for the same posting).
- no company → `profile/research/<title-slug>.md` (same slug rules applied to the title; create `profile/research/`).

## Step 2 — Worker `cv-researcher` (Agent tool)

```
Research what this role requires so the candidate can emphasize matching experience.
title: <title>
company: <company or "unknown">
jd_path: <applications/<slug>/jd.md or "none">
history_path: profile/history.md
output_path: <output path from step 1>
Write research.md with: ## Role Requirements, ## Must-have Keywords, ## Nice-to-have, ## Company Notes (or "unknown company"), ## Suggested Emphasis (which items in history.md to foreground; cite them, never invent experience). Use web search for current postings and the company; read only the files listed. Return a summary of at most 10 lines.
```

## Step 3 — Present

Show the must-have keywords and the suggested emphasis list. If the suggested emphasis mentions experience not present in `profile/history.md`, say so explicitly.

## End

Saved: the research.md path (and `jd.md` if captured).
Related line → Phase C (fit the resume to this role). Then stop (SKILL.md Step 3).
