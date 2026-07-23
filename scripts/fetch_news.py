#!/usr/bin/env python3
"""
M23 / DRC news tracker — free-tier data pipeline.

Pulls from:
  - Google News RSS (no key)
  - GDELT DOC API (no key)
  - ReliefWeb / UN OCHA country RSS (no key)
  - Direct outlet RSS (Al Jazeera, Africanews) filtered by keyword

Dedupes against existing data/events.json, merges, caps size, writes back.
Designed to run unattended on a GitHub Actions cron.
"""

import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "events.json"
MAX_ITEMS = 800          # cap so the JSON / page never grows unbounded
MAX_AGE_DAYS = 120        # drop items older than this on every run
REQUEST_TIMEOUT = 20
USER_AGENT = "m23-drc-tracker/1.0 (+https://github.com/; free, non-commercial monitoring)"

# Keyword gate. GDELT/Google News are already query-scoped, but generic
# outlet firehoses (Al Jazeera "all", Africanews "all") need this filter.
KEYWORDS = [
    "m23", "congo", "drc", "d.r.c", "kinshasa", "goma", "bukavu",
    "north kivu", "south kivu", "rwanda-backed", "fardc", "kivu",
]

GOOGLE_NEWS_QUERIES = [
    'M23 Congo',
    'M23 DRC',
    '"Democratic Republic of Congo" conflict',
    'Goma Congo',
]

GDELT_QUERIES = [
    'M23 Congo',
    'M23 rebels DRC',
]

RELIEFWEB_FEEDS = [
    # Country-specific ReliefWeb updates (DRC = "cod")
    "https://reliefweb.int/updates/rss.xml?search=country_name%3A%22Democratic%20Republic%20of%20the%20Congo%22",
]

GENERIC_FEEDS = [
    # (name, url) — filtered locally by KEYWORDS since they're general firehoses
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Africanews", "https://www.africanews.com/feed/rss"),
]


def log(msg):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}", file=sys.stderr)


def normalize_title(title):
    """Collapse whitespace/punctuation so near-identical headlines dedupe."""
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def contains_keyword(*texts):
    blob = " ".join(t or "" for t in texts).lower()
    return any(k in blob for k in KEYWORDS)


def parse_feed_entries(feed_url, source_name, require_keyword=False):
    items = []
    try:
        parsed = feedparser.parse(feed_url, agent=USER_AGENT, request_headers={"User-Agent": USER_AGENT})
    except Exception as e:
        log(f"ERROR parsing {source_name} ({feed_url}): {e}")
        return items

    for entry in parsed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = re.sub(r"<[^>]+>", "", entry.get("summary", "") or "").strip()
        if not title or not link:
            continue
        if require_keyword and not contains_keyword(title, summary):
            continue

        published_dt = None
        for key in ("published_parsed", "updated_parsed"):
            if entry.get(key):
                published_dt = datetime.fromtimestamp(time.mktime(entry[key]), tz=timezone.utc)
                break
        if published_dt is None:
            published_dt = datetime.now(timezone.utc)

        # Google News RSS wraps the real source in the title as "Headline - Outlet"
        display_source = source_name
        if source_name == "Google News" and " - " in title:
            title, _, outlet = title.rpartition(" - ")
            display_source = outlet.strip()

        items.append({
            "title": title.strip(),
            "link": link,
            "summary": summary[:400],
            "source": display_source,
            "published": published_dt.isoformat(),
        })
    return items


def fetch_google_news():
    all_items = []
    for q in GOOGLE_NEWS_QUERIES:
        url = (
            "https://news.google.com/rss/search?q="
            + urllib.parse.quote(q)
            + "&hl=en-US&gl=US&ceid=US:en"
        )
        log(f"Fetching Google News: {q}")
        all_items.extend(parse_feed_entries(url, "Google News"))
    return all_items


def fetch_gdelt():
    all_items = []
    for q in GDELT_QUERIES:
        url = (
            "https://api.gdeltproject.org/api/v2/doc/doc?query="
            + urllib.parse.quote(q)
            + "&mode=artlist&maxrecords=75&format=json&sort=datedesc"
        )
        log(f"Fetching GDELT: {q}")
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log(f"ERROR fetching GDELT ({q}): {e}")
            continue

        for art in data.get("articles", []):
            title = (art.get("title") or "").strip()
            link = (art.get("url") or "").strip()
            if not title or not link:
                continue
            seendate = art.get("seendate")  # e.g. "20250723T120000Z"
            try:
                published_dt = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                published_dt = datetime.now(timezone.utc)

            all_items.append({
                "title": title,
                "link": link,
                "summary": "",
                "source": art.get("domain", "GDELT"),
                "published": published_dt.isoformat(),
            })
    return all_items


def fetch_reliefweb():
    all_items = []
    for url in RELIEFWEB_FEEDS:
        log(f"Fetching ReliefWeb: {url}")
        all_items.extend(parse_feed_entries(url, "ReliefWeb / OCHA"))
    return all_items


def fetch_generic():
    all_items = []
    for name, url in GENERIC_FEEDS:
        log(f"Fetching {name} (filtered)")
        all_items.extend(parse_feed_entries(url, name, require_keyword=True))
    return all_items


def load_existing():
    if DATA_PATH.exists():
        try:
            return json.loads(DATA_PATH.read_text())
        except Exception:
            return {"items": []}
    return {"items": []}


def main():
    existing = load_existing()
    existing_items = existing.get("items", [])

    fetched = []
    fetched.extend(fetch_google_news())
    fetched.extend(fetch_gdelt())
    fetched.extend(fetch_reliefweb())
    fetched.extend(fetch_generic())

    log(f"Fetched {len(fetched)} raw items this run; {len(existing_items)} already stored.")

    combined = existing_items + fetched

    # Dedupe: prefer link match first, fall back to normalized-title match.
    seen_links = set()
    seen_titles = set()
    deduped = []
    for item in combined:
        link = item.get("link", "")
        norm_title = normalize_title(item.get("title", ""))
        if not link or not norm_title:
            continue
        if link in seen_links or norm_title in seen_titles:
            continue
        seen_links.add(link)
        seen_titles.add(norm_title)
        deduped.append(item)

    # Drop stale items, sort newest first, cap size.
    cutoff = datetime.now(timezone.utc).timestamp() - MAX_AGE_DAYS * 86400
    def pub_ts(item):
        try:
            return datetime.fromisoformat(item["published"]).timestamp()
        except Exception:
            return 0

    deduped = [i for i in deduped if pub_ts(i) >= cutoff]
    deduped.sort(key=pub_ts, reverse=True)
    deduped = deduped[:MAX_ITEMS]

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "count": len(deduped),
        "items": deduped,
    }

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    log(f"Wrote {len(deduped)} items to {DATA_PATH}")


if __name__ == "__main__":
    main()
