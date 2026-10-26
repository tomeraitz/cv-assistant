# Job-posting extraction

Used by Phase C step 1 and Phase D. Produces the fields of `applications/<slug>/jd.md`.

## Sources, in order
1. Browser tools available (any browser MCP tools or a Cowork browser): open the URL in the user's logged-in browser, wait for the page to load, read the visible text. Login wall or CAPTCHA → pause and ask the user to handle it in the browser; then continue. Expand "show more" / "see full description" controls before reading.
2. No browser tools: WebFetch the URL. A login page, an empty description, or an error → ask the user to paste the posting text.
3. Pasted text: use as-is.

## Fields

| Field | How to get it | If absent |
|---|---|---|
| title | page heading / first line of the posting; strip suffixes like "(Remote)", "- Tel Aviv", requisition IDs | ask the user |
| company | employer name near the title, page title, or URL (`/company/<name>/`, `jobs.<company>.com`) | ask the user |
| location | location line; keep "Remote"/"Hybrid" | "not stated" |
| seniority | from title or text: intern / junior / mid / senior / staff / lead / manager | "not stated" |
| must-have | "Requirements", "What you'll need", "Qualifications", "Must have" lists | derive from the text; mark "(inferred)" |
| nice-to-have | "Nice to have", "Preferred", "Bonus", "Advantage" lists | empty |
| keywords | technologies, methods, domains and certifications named anywhere in the text, deduplicated, original spelling | — |
| full text | the complete posting body: description, responsibilities, requirements, benefits. Exclude navigation, cookie banners, "similar jobs", ads | — |

## Rules
- Do not summarize the full text; keep it complete so workers can re-read it.
- Keep the source URL and the capture date (`YYYY-MM-DD`).
- Hebrew or other non-English postings: keep the full text in the original language; write title/company/keywords in English for the slug and the reports.
- Never fetch pages other than the posting URL (no company browsing in Phase C; that is Phase D).
