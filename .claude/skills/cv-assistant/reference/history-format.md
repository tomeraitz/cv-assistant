# history.md format

`profile/history.md` is the single source of truth for every factual claim in a resume. Workers may only use facts written here. Empty skeleton: `templates/history.template.md`.

## Structure (headings are fixed; order is fixed)

```markdown
# <Name> - Professional History

## Education
- <Degree>, <Institution>, <start> – <end> (GPA/honors if any)
- <Certification>, <Issuer>, <year>

## Career Journey
### <Company> - <Role> (<start> – <end>)
- Scope: <what the role owned; team size; who you reported to / led>
- Stack: <languages, frameworks, cloud, tools>
- Result: <measurable outcome — number, %, time, money, users>
- Result: <...>
- Context: <optional: product, domain, company size>

### <Company> - <Role> (<start> – <end>)
...

## Projects
### <Project name> (<year>)
- What: <one line>
- Stack: <...>
- Result: <measurable outcome or link>

## Skills
- <Category>: <comma-separated skills>  (e.g. Languages, Backend, Data/ML, Cloud, Tools)

## Languages
- <Language> – <level>

## Looking For
- Target titles: <title 1>, <title 2>
- Seniority / type: <e.g. senior, full-time, remote>
- Emphasize: <skills or themes to foreground>
```

## Rules

- Dates: `MMM YYYY` or `YYYY`; current role ends with `Present`.
- Roles in `## Career Journey` are newest first. A role block is identified by its `### <Company> - <Role>` line; B1/B2/B3 in Phase B add, edit or delete whole blocks.
- Every `Result:` bullet contains at least one number supplied by the user. No number → write the qualitative result without a number; never estimate.
- Unknown items during onboarding are marked `_missing_` and asked about in the interview; a saved file must contain no `_missing_` markers (delete the bullet instead).
- `## Looking For → Target titles` mirrors `profile/profile.json.target_titles`; Phase B4 updates both.
- Plain markdown; no tables, no HTML, no personal identifiers beyond the name (contact details stay in the PDF template).
