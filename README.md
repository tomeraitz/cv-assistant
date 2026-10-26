# cv-assistant

A Claude Code skill that keeps your master resume up to date and tailors it to specific job postings, using a small team of worker subagents.

## What it does

- **Onboard (Phase A)** – builds `profile/` from your career history and your current resume PDF, including a coordinate map of the editable sections.
- **Update (Phase B)** – adds, edits or removes positions and target titles in `profile/history.md`, then regenerates `profile/<Name> CV.pdf` (with a dated backup).
- **Fit a job (Phase C)** – reads a job description, scores the match, rewrites sections with only claims backed by your history, runs an ATS check, writes a tailored PDF into `applications/<company>-<job-title>/`, and verifies the PDF against your history before handing it to you.
- **Research (Phase D)** – gathers role requirements, must-have keywords and company notes into `research.md` for a title (and optionally a company / job posting).

Every phase ends with the list of files it saved and a short list of related things it can do next.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Python 3.10+ with `pip install pymupdf` (PDF reading and writing)
- Optional: [Claude in Chrome](https://docs.anthropic.com/en/docs/claude-code/chrome) so the skill can read job postings straight from your browser tab

## Install

### 1. Project use (recommended)

```bash
git clone https://github.com/tomeraitz/cv-assistant.git
cd cv-assistant
pip install pymupdf
claude
```

Inside Claude Code type `/cv-assistant`, or just describe what you want ("fit my resume to this job: <url>", "add my new position", "research AI Engineer roles"). The first run launches onboarding and creates `profile/`.

### 2. Personal install

```bash
git clone https://github.com/tomeraitz/cv-assistant.git ~/.claude/skills/cv-assistant
```

This makes the skill available in every project, but the worker agents (`.claude/agents/`) and the PDF helpers (`lib/`, `assets/fonts/`) are referenced relative to the project root, so you still need to run `claude` from a checkout of this repo (or copy `.claude/agents/`, `lib/` and `assets/` into your project). Project use is simpler.

### 3. Claude Desktop / Cowork (plugin)

In Claude Desktop open **Customize → Plugins**, select **Add marketplace**, enter `tomeraitz/cv-assistant`, then install **cv-assistant** from that marketplace. Alternatively zip the repository and use **Upload plugin**. In Claude Code the same plugin installs with:

```
/plugin install cv-assistant --marketplace tomeraitz/cv-assistant
```

PDF generation requires Python and `pymupdf` in the environment where Claude runs; in the Cowork sandbox this is untested.

## Browser setup (optional)

To let the skill read job postings from your open browser tab, install the [Claude in Chrome](https://docs.anthropic.com/en/docs/claude-code/chrome) extension and enable it in Claude Code. Without the browser extension the skill falls back to fetching the URL, and finally to asking you to paste the posting text.

## Data layout

```
profile/                      # git-ignored – your personal data
  history.md                  # free-form career history (source of truth for every claim)
  <Name> CV.pdf               # the PDF template that tailored resumes are derived from
  template-coords.json        # coordinate map of editable sections in the template PDF
  profile.json                # name, target titles, language
applications/                 # git-ignored – one folder per job
  <company>-<job-title>/
    jd.md  match-report.md  rewrite.md  ats-report.md  changes.json
    research.md  accuracy-check.md  <Name> CV.pdf
```

Both `profile/` and `applications/` are listed in `.gitignore`, so forking or pushing this repo never publishes your data.

## How the PDF template works

`profile/<Name> CV.pdf` is edited in place rather than regenerated. During onboarding the skill runs `lib/inspect_template.py` to list every text span on the page and records each editable region (summary, bullets of each role, skills blocks) in `profile/template-coords.json` with its bounding box, font-size range and the original text length.

When a resume is tailored, `lib/apply_pdf_changes.py` redacts the original region and re-inserts the new text in the same font and colour. The font size is chosen adaptively to fit the box, so replacement text should stay within **±10 % of the original character count** of that section – otherwise the text shrinks and looks inconsistent. Short exact-text edits (for example a job title) are handled with `single_replacements`. The result is compressed and the requested keywords are verified to be present.

## Privacy

Your history, resume and application files stay on your machine. The only place they go is into the prompts sent to the Claude API (and, if you use research or browser features, the web pages those fetch). Nothing is uploaded elsewhere by this project.

## Contributing

Issues and pull requests are welcome. By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

MIT – see [LICENSE](LICENSE).
