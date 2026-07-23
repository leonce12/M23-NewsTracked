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

X/Twitter is intentionally **not** in the pipeline — free embeds don't support
keyword/hashtag feeds, and Nitter-style scraping is too fragile to depend on
after X's rate-limiting changes. If you want specific accounts (a UN
spokesperson, a journalist on the ground), embed them individually with
[publish.x.com](https://publish.x.com) directly in `index.html` — that part
stays genuinely free and stable.

## 1. Get this running (5 minutes)

1. Create a new **public** GitHub repo (public repos get unlimited free
   Actions minutes; private repos get 2,000 min/month, which is still plenty
   at this schedule, but public is simplest).
2. Push everything in this folder to the repo root.
3. In the repo, go to **Settings → Pages** → set source to **Deploy from a
   branch**, branch `main`, folder `/ (root)`. Save.
4. Go to **Settings → Actions → General → Workflow permissions** → select
   **Read and write permissions**. This lets the workflow commit updated
   data back to the repo.
5. Go to the **Actions** tab → select **Update M23/DRC feed** → click
   **Run workflow** to trigger the first fetch manually (don't wait for the
   cron).
6. Once it finishes (~30–60 seconds), your site is live at
   `https://<your-username>.github.io/<repo-name>/`.

After that, it runs itself: every 3 hours the workflow fetches, dedupes,
and commits `data/events.json` if anything changed. Nothing to maintain.

## 2. Repo layout

```
.
├── .github/workflows/update.yml   # the cron job
├── scripts/fetch_news.py          # fetch + dedupe + write logic
├── data/events.json               # generated data (committed by the bot)
├── index.html                     # the dashboard (no build step)
└── requirements.txt
```

## 3. Customizing

- **Change keywords / queries**: edit `GOOGLE_NEWS_QUERIES`, `GDELT_QUERIES`,
  and `KEYWORDS` at the top of `scripts/fetch_news.py`.
- **Change schedule**: edit the `cron` line in
  `.github/workflows/update.yml` (currently every 3 hours). GitHub's minimum
  interval is 5 minutes, but don't go under ~15–30 minutes — you'll hit
  GDELT's fair-use expectations and gain nothing, since news doesn't move
  that fast.
- **Add ACLED conflict-event data as a map layer**: ACLED is free with
  registration but needs an API key, which is why it's not wired in by
  default (keeps this repo genuinely zero-config). If you want it: sign up
  at [acleddata.com](https://acleddata.com), add `ACLED_KEY` as a GitHub
  Actions secret, and add a `fetch_acled()` function following the same
  pattern as `fetch_gdelt()`.
- **Add specific X/Twitter accounts**: use
  [publish.x.com](https://publish.x.com) to generate an embed snippet, then
  drop it into `index.html` wherever you'd like it to sit (e.g. a sidebar).
- **Cap on stored items / staleness**: `MAX_ITEMS` and `MAX_AGE_DAYS` in
  `scripts/fetch_news.py` control how large `data/events.json` grows.

## 4. Known limitations

- **Google News RSS** is unofficial and can occasionally rate-limit or
  reshuffle result ordering — the script treats it as best-effort, not
  guaranteed-complete.
- **GDELT** ranks by relevance/recency heuristics, not a strict boolean
  match, so a small amount of noise can slip through despite the keyword
  queries.
- **ReliefWeb** updates are slower (situation reports, not breaking news) —
  treat it as a lagging but higher-quality layer, not a real-time source.
- This is an **aggregator, not a verification tool**. It surfaces headlines
  from open sources; it doesn't fact-check or corroborate them. Say so to
  anyone else who uses the page (the footer already does).

## 5. Running the fetch locally (optional)

```bash
pip install -r requirements.txt
python scripts/fetch_news.py
python -m http.server 8000   # then open http://localhost:8000
```
