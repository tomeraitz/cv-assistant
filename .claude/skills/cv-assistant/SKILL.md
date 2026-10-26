---
name: cv-assistant
description: Resume/CV assistant. Use when the user wants to tailor a resume to a job posting (text or URL), add or update a position in their resume, change the job title they target, create a resume profile from scratch, or research a role. Triggers: resume, CV, job description, tailor, fit, apply, new position, promotion.
argument-hint: [job URL or description | update | onboard | research]
allowed-tools: Read, Write, Glob, Bash, WebFetch, Agent
license: MIT
compatibility: Needs Python 3 + PyMuPDF for PDF generation; browser tools optional
---

# cv-assistant

One entry point, four phases. All paths are relative to the project root (where `claude` was launched).
When running as an installed plugin (Claude Desktop / marketplace), the code lives at `${CLAUDE_PLUGIN_ROOT}`: run the helpers as `python "${CLAUDE_PLUGIN_ROOT}/lib/<script>.py"` and tell worker agents that path; `profile/` and `applications/` stay in the user's working folder.
User data lives only in `profile/` and `applications/` (git-ignored). Never store personal data inside `.claude/`.

## Step 0 — Profile check

Glob `profile/profile.json`.
- Missing → go to Phase A (onboard), regardless of what the user asked.
- Present → Read it silently (`name`, `target_titles`, `language`). Do not announce it.

Naming used by every phase: `<Name>` = `profile.json.name`. The resume template is `profile/<Name> CV.pdf`; every tailored resume is written as `applications/<slug>/<Name> CV.pdf`.

## Step 1 — Route by intent

Route from the user's message before showing any menu. The user never needs a command.

| User says (examples) | Phase |
|---|---|
| "fit / tailor my CV to this job", pastes a job description, gives a URL | C — `phases/fit-resume.md` |
| "add a new job / position / role", "I got promoted", "update my experience", "I want to target a new job title" | B — `phases/update-resume.md` |
| "I don't have a resume", "start from scratch", or `profile/` does not exist | A — `phases/onboard.md` |
| "what does a <title> need", "research this role" | D — `phases/research-role.md` |
| unclear, or invoked bare as `/cv-assistant` | menu below |

Menu (AskUserQuestion, exactly these four options):
1. Fit to a job
2. Update my resume (new position / new target title)
3. Create my profile
4. Research a role

If a later message matches a different phase while one is in progress: finish the current phase, then point to a new conversation in Step 3. No phase switching inside one conversation.

## Step 2 — Run the phase

Read `.claude/skills/cv-assistant/phases/<x>.md` before executing a phase, and only that phase file. Phase files tell you which `reference/*.md` files to read and when.

Job-posting URLs (Phase C): If browser tools (e.g. claude-in-chrome MCP tools or a Cowork browser) are available use them for URLs; else WebFetch; else ask the user to paste the posting. If none are available and the user gave a URL, mention once that enabling the Claude in Chrome extension lets the skill read postings from the browser.

Rules that apply in every phase:
- Truthfulness: `reference/truthfulness-policy.md`. Only facts from `profile/history.md` or stated by the user in this conversation go into a resume. Never invent numbers.
- Interviews: one topic per turn, via AskUserQuestion or a plain question.
- Nothing is written to `profile/` or to a PDF before the user explicitly approves.
- Worker subagents (`hiring-manager-reviewer`, `rewrite-resume`, `application-tracking-system`, `pdf-writer`, `cv-researcher`) are invoked with the Agent tool. Each task prompt lists every input and output path explicitly; workers write exactly one file and return a short summary.

## Step 3 — End of phase (every phase ends here)

1. List every file saved in this phase, as paths.
2. One line: `Related: I can also <next phase>. Start a new conversation and ask for it.`
   - After A → fit the resume to a job (Phase C).
   - After B → fit the updated resume to a job (Phase C).
   - After C → add experience mentioned in chat but missing from `profile/history.md` (Phase B); otherwise research a role (Phase D).
   - After D → fit the resume to this role (Phase C).
3. Stop. No auto-chaining into the next phase.
