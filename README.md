# M23 / DRC Situation Feed

A fully free, no-API-key news tracker for the M23/DRC conflict. A GitHub Actions
cron job polls open sources every 3 hours, dedupes and merges results into
`data/events.json`, and a static page (served by GitHub Pages) renders it.

**Cost: $0.** No billing account, no API keys, nothing to rotate.

## Sources

| Source | What it gives you | Auth |
|---|---|---|
| Google News RSS | Broad outlet coverage for a few keyword queries | None |
| [GDELT DOC API](https://www.gdeltproject.org/) | Global news search by keyword, frequent updates | None |
| ReliefWeb / UN OCHA RSS | DRC-specific humanitarian situation reports | None |
| Al Jazeera / Africanews RSS | Direct outlet feeds, filtered locally by keyword | None |
