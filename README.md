# Credit Caddy News Feed

Static news feed for the [Credit Caddy](https://github.com/justincoleman) iOS app.
Curated every 6 hours by a Claude scheduled task from credit-card-focused RSS feeds.

**Live feed:** [`articles.json`](./articles.json)

## Schema

```json
{
  "updatedAt": "ISO 8601 timestamp — when the feed was last regenerated",
  "articles": [
    {
      "id": "16-char stable hash of url",
      "title": "Article headline",
      "summary": "One-sentence summary",
      "url": "https://canonical-article-url",
      "thumbnailUrl": "https://image-url or null",
      "category": "News | Tips | Deals | Card Updates",
      "publishedAt": "ISO 8601 timestamp — original publication date",
      "source": "Publisher name, e.g. Doctor of Credit"
    }
  ]
}
```

## Categories

- **News** — industry/bank news, regulatory changes, data breaches
- **Tips** — strategy, how-to, optimization
- **Deals** — specific SUBs, elevated offers, targeted bonuses, retention offers
- **Card Updates** — new card launches, refreshes, benefit changes on a specific card

Articles that don't cleanly fit one category are skipped.

## Retention

Rolling 30-day window, capped at 50 newest articles.
