#!/usr/bin/env python3
"""News feed curator. Runs in GitHub Actions every 6 hours.

Fetches RSS from 6 credit-card / loyalty publishers, dedups against the
existing articles.json in cwd, categorizes, prunes >30 days, caps at 50,
and writes the result back. The workflow handles git commit + push.
"""

import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

FEEDS = [
    ("Doctor of Credit",   "https://www.doctorofcredit.com/feed/"),
    ("The Points Guy",     "https://thepointsguy.com/feed/"),
    ("One Mile at a Time", "https://onemileatatime.com/feed/"),
    ("View from the Wing", "https://viewfromthewing.com/feed/"),
    ("Frequent Miler",     "https://frequentmiler.com/feed/"),
    ("AwardWallet",        "https://awardwallet.com/blog/feed/"),
]

# Browser-like UA — some publishers' WAFs block default urllib UA
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15"
)

NOW = datetime.now(timezone.utc)
MAX_AGE = timedelta(days=14)
PRUNE_AGE = timedelta(days=30)
CAP = 50

# ----- helpers --------------------------------------------------------------


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def first_sentence(s, cap=140):
    s = s.strip()
    m = re.search(r"[.!?]\s", s[:200])
    if m:
        s = s[:m.end()].strip()
    if len(s) > cap:
        s = s[:cap - 1].rstrip() + "…"
    return s


def stable_id(url):
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def thumb_from_item(item):
    for media in item.findall("media:content", ATOM_NS):
        url = media.get("url")
        if url and (media.get("type", "").startswith("image") or url.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
            return url
    for enc in item.findall("enclosure"):
        if enc.get("type", "").startswith("image"):
            url = enc.get("url")
            if url:
                return url
    desc = item.findtext("description") or ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    return m.group(1) if m else None


# ----- categorization -------------------------------------------------------

CARD_KEYWORDS = re.compile(
    r"\b(amex|american express|chase|citi|capital one|cap one|wells fargo|us bank|bilt|"
    r"barclays|barclaycard|sapphire|reserve|preferred|platinum|gold card|hilton|marriott|"
    r"hyatt|delta|united|southwest|jetblue|aspire|venture|freedom|ink|business gold|"
    r"business platinum|edit|skymiles|aadvantage|skyclub|miles|points|cardmember|credit card|"
    r"annual fee|signup bonus|sub|welcome offer|membership rewards|ultimate rewards|thankyou|"
    r"capital one travel|portal|transfer partner|elevated offer|targeted)\b",
    re.I,
)

DEAL_KEYWORDS = re.compile(
    r"\b(\$\d+|\d+%|bonus|offer|deal|elevated|limited time|earn \d+|points back|cash back|"
    r"targeted|special|promo|limited[- ]time|spend \$|stack)\b",
    re.I,
)
TIPS_KEYWORDS = re.compile(
    r"\b(guide|how to|should you|best way|ultimate|strategy|tips|complete|reviewed|review|"
    r"maximize|optimize|sweet spot|hidden|understand|explained|when to|where to|comparison|"
    r"vs\.|compared)\b",
    re.I,
)
CARD_UPDATE_KEYWORDS = re.compile(
    r"\b(card refresh|new card|launches?|relaunch|introduces?|debuts?|"
    r"benefits? (change|update|added|removed)|refreshed|revamp|relaunch|"
    r"adds? .* benefit|adds? .* credit)\b",
    re.I,
)
NEWS_KEYWORDS = re.compile(
    r"\b(reduces|increases|shifts?|category change|devalu|enhanc|breach|hack|lawsuit|"
    r"class action|regulator|FTC|CFPB|merger|acquisition|partnership|shutter|closes|"
    r"discontinues|ends|expires?|reinstates?|investigat|fraud)\b",
    re.I,
)

SKIP_KEYWORDS = re.compile(
    r"\b(trump|biden|congress|whitehouse|white house|deport|ice agent|iran|russia|ukraine|"
    r"en-suite|cabin design|aircraft seat|boeing 737|airbus a32\d|new route|launches route|"
    r"inaugural flight|fleet expansion|airline ceo|ceo says)\b",
    re.I,
)


def categorize(title, summary):
    text = f"{title} {summary}"

    if SKIP_KEYWORDS.search(text) and not (DEAL_KEYWORDS.search(text) or "credit card" in text.lower() or "points" in text.lower()):
        return None

    if not CARD_KEYWORDS.search(text):
        return None

    # Deals before Card Updates because lots of deals mention card names
    if DEAL_KEYWORDS.search(text) and not CARD_UPDATE_KEYWORDS.search(title):
        return "Deals"
    if CARD_UPDATE_KEYWORDS.search(title):
        return "Card Updates"
    if NEWS_KEYWORDS.search(title):
        return "News"
    if TIPS_KEYWORDS.search(text):
        return "Tips"
    return None


# ----- main -----------------------------------------------------------------


def main():
    articles_path = os.environ.get("ARTICLES_PATH", "articles.json")
    with open(articles_path) as f:
        feed = json.load(f)
    existing_urls = {a["url"] for a in feed["articles"]}
    print(f"Existing articles: {len(feed['articles'])}", file=sys.stderr)

    candidates = []
    fetch_results = []

    for source_name, url in FEEDS:
        try:
            raw = fetch(url)
            root = ET.fromstring(raw)
            fetch_results.append((source_name, "ok", None))
        except (urllib.error.URLError, urllib.error.HTTPError, ET.ParseError, TimeoutError) as e:
            fetch_results.append((source_name, "fail", str(e)[:80]))
            continue
        except Exception as e:
            fetch_results.append((source_name, "fail", f"unexpected: {type(e).__name__}: {str(e)[:60]}"))
            continue

        items = root.findall(".//item") or root.findall(".//atom:entry", ATOM_NS)
        kept = 0
        for it in items:
            title = (it.findtext("title") or it.findtext("atom:title", namespaces=ATOM_NS) or "").strip()
            link = (it.findtext("link") or "").strip()
            if not link:
                link_el = it.find("atom:link", ATOM_NS)
                if link_el is not None:
                    link = link_el.get("href", "")
            link = link.strip()

            pd_str = it.findtext("pubDate") or it.findtext("atom:published", namespaces=ATOM_NS) or it.findtext("dc:date", namespaces=ATOM_NS)
            pd = parse_date(pd_str)

            desc_raw = it.findtext("description") or it.findtext("atom:summary", namespaces=ATOM_NS) or ""
            desc = strip_html(desc_raw)

            if not (title and link and pd):
                continue
            if NOW - pd > MAX_AGE:
                continue
            if link in existing_urls:
                continue

            cat = categorize(title, desc)
            if cat is None:
                continue

            candidates.append({
                "id": stable_id(link),
                "title": title,
                "summary": first_sentence(desc, 140) or title,
                "url": link,
                "thumbnailUrl": thumb_from_item(it),
                "category": cat,
                "publishedAt": pd.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": source_name,
            })
            kept += 1
        print(f"  [{source_name}] kept {kept}/{len(items)} items", file=sys.stderr)

    print(f"\nFetch results:", file=sys.stderr)
    for name, status, err in fetch_results:
        line = f"  {status:4s}  {name}"
        if err:
            line += f"  ({err})"
        print(line, file=sys.stderr)

    print(f"\nNew candidates: {len(candidates)}", file=sys.stderr)

    # Merge: existing + new, sort desc, prune >30d, cap
    combined = feed["articles"] + candidates
    cutoff = NOW - PRUNE_AGE
    combined = [a for a in combined if parse_date(a["publishedAt"]) and parse_date(a["publishedAt"]) > cutoff]
    combined.sort(key=lambda a: a["publishedAt"], reverse=True)
    combined = combined[:CAP]

    new_feed = {
        "updatedAt": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "articles": combined,
    }

    with open(articles_path, "w") as f:
        json.dump(new_feed, f, indent=2)
        f.write("\n")

    added = len(candidates)
    pruned = len(feed["articles"]) + added - len(combined)
    final = len(combined)
    print(f"\nFinal: total={final}  added={added}  pruned={pruned}", file=sys.stderr)

    # Emit summary for the workflow's commit message
    summary_path = os.environ.get("GITHUB_OUTPUT")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"total={final}\n")
            f.write(f"added={added}\n")
            f.write(f"pruned={pruned}\n")


if __name__ == "__main__":
    main()
