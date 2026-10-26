# Truthfulness policy

Pick, don't invent. A tailored resume selects and rephrases real experience; it never adds experience.

## Allowed
- Rewording a fact from `profile/history.md` (or stated by the user in this conversation and about to be added to history.md).
- Choosing which real facts to show for a given job.
- Using a job posting's terminology for a thing the user actually did (e.g. "RAG pipeline" for a retrieval + LLM system described in history.md).
- Reordering bullets, merging two real bullets, dropping bullets.

## Not allowed
- Numbers that are not in history.md or given by the user (no estimates, no "~", no rounding up).
- Tools, languages, frameworks, certifications, degrees, titles, employers or dates not in history.md.
- Upgrading scope ("led" when history says "contributed"; "owned" when it says "helped"; team sizes not stated).
- Keywords from the job posting with no supporting evidence. They go under `## Keywords Not Added`.

## When evidence is missing
- Interactive phases (A, B, C approval gate): ask the user. One question, with the specific claim.
- Workers (no user access): leave the claim out and list it under `## Keywords Not Added` with the reason "no evidence in history".

## Verification (Phase C step 5)
Every factual claim in the final PDF text is traced to a line in history.md and recorded in `accuracy-check.md`. An unsupported claim triggers one regeneration; a second one is reported to the user as FLAGGED, never silently kept.
