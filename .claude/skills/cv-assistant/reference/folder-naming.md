# Application folder naming

Every application lives in `applications/<company>-<job-title>/`.

## Slug rule
1. Start from `<company> <job title>` (company first).
2. Lowercase.
3. ASCII only: transliterate Latin accents (`é`→`e`); drop characters with no ASCII form (Hebrew, CJK, symbols). If the whole company or title drops out, use its English name as asked from the user or extracted from the URL.
4. Spaces → `-`.
5. Strip punctuation (`,.()&/|:'"!?` etc.). `&` → `-`, `+` in tech names (`c++`) is dropped (`c`).
6. Collapse repeated `-`; trim leading/trailing `-`.
7. Max 60 characters; cut at the last `-` before the limit.
8. Existing folder for a different posting → append `-2`, then `-3`, …

## Examples
| Company | Title | Slug |
|---|---|---|
| Acme | AI Engineer | `acme-ai-engineer` |
| Acme Corp. | Senior Backend Engineer (Remote) | `acme-corp-senior-backend-engineer-remote` |
| Müller & Söhne | Data Engineer | `muller-sohne-data-engineer` |
| Acme | AI Engineer (second posting) | `acme-ai-engineer-2` |

## Other uses
- Phase D without a company: `profile/research/<title-slug>.md`, same rules applied to the title alone.
- Output PDF name inside the folder is not slugged: `<Name> CV.pdf`, `<Name>` = `profile.json.name` in original casing (only characters invalid in file names, `\/:*?"<>|`, are removed). Same name in every application folder; the folder slug tells the jobs apart.
