# Discord Digest Bot Design — 2026-08-01

## Overview

GitHub Actions + Discord Webhook system tự động post tin tức AOV với AI tóm tắt chi tiết, tier changes, meta analysis.

## Architecture

```
GitHub Actions (7:00 AM GMT+7 daily)
│
├─ 1. hero_snapshot.py — Lưu heroes.json → heroes_snapshot.json
├─ 2. news_crawler.py — Crawl news mới (RSS + scrape)
├─ 3. youtube_rss_fetcher.py — Crawl video mới
├─ 4. update_hero_trends.py — Update tier mới
├─ 5. discord_digest.py — Đọc data → LLM → post Discord
└─ 6. git commit + push → Vercel deploy
```

## Tech Stack

- **Runtime:** GitHub Actions (Python 3.10)
- **LLM:** 9router (OpenAI-compatible endpoint)
- **Discord:** Webhook API (không cần bot token)
- **Data:** JSON files (news.json, heroes.json, videos.json)
- **Schedule:** Cron `0 0 * * *` (00:00 UTC = 07:00 GMT+7)

## Features

### 1. Per-News AI Digest

Mỗi tin tức mới → 1 Discord embed riêng với:
- AI tóm tắt chi tiết (150-200 từ)
- Stats changes cụ thể (damage, cooldown, %)
- Hero mentions + thumbnails
- Tier predictions
- Source image + link

**Categories & Templates:**

| Category | Template Style | Role Mention |
|----------|---------------|--------------|
| Patch Notes | Stats table, buff/nerf boxes, meta impact | @Patch-Notes |
| Esports | Match results, MVP, tier impact | @Esports |
| Skin | Info box, effects breakdown, verdict | @Skin-Mới |
| Sự Kiện | Timeline, prizes, how to join | @Sự-Kiện |
| Tướng Mới | Stats, skills, counters, synergies | @Tướng-Mới |
| Meta Analysis | Tier changes, meta shift, recommendations | @Meta-Analysis |

### 2. Tier Changes Digest

So sánh heroes.json snapshot (trước update) vs current:
- Detect: S→A (nerf), A→S (buff), etc.
- Embed với hero thumbnails
- Giải thích lý do (hot_count, score)
- Meta analysis tổng hợp

### 3. Meta Overview

AI phân tích xu hướng từ:
- News articles (24h qua)
- Video titles (7 ngày qua)
- Tier changes
- Keyword frequency (buff/nerf/meta/etc.)

## Discord Embed Design

**Visual Style:**
- Box characters (`┌─┐`) tạo border
- Emoji color coding: 🟢 buff, 🔴 nerf, 🟡 neutral
- Arrow indicators: ⬆️ ⬇️ với percentage
- Bold tướng tên + chiêu
- Verdict line ngắn gọn, actionable
- Code block cho meta analysis

**Embed Colors:**
- Patch Notes: `#ff6b6b` (red)
- Esports: `#4ecdc4` (teal)
- Skin: `#ffe66d` (yellow)
- Sự Kiện: `#95e1d3` (mint)
- Tướng Mới: `#f38181` (coral)
- Meta Analysis: `#aa96da` (purple)

**No @everyone** — chỉ role mentions:
```
@Patch-Notes
@Esports
@Skin-Mới
@Sự-Kiện
@Tướng-Mới
@Meta-Analysis
```

User tự assign role → nhận notification category quan tâm.

## Implementation Details

### Files

| File | Purpose |
|------|---------|
| `.github/workflows/discord-digest.yml` | Cron job orchestration |
| `crawler/discord_digest.py` | Main script: fetch → LLM → post |
| `crawler/hero_snapshot.py` | Snapshot heroes.json trước update |
| `crawler/digest_config.json` | Config: webhook, LLM endpoint, role IDs |

### `discord_digest.py` Logic

```python
# 1. Load config
config = load("digest_config.json")

# 2. Detect new news (crawled_at > last_run timestamp)
last_run = load_last_run_timestamp()
new_news = [n for n in news if n['crawled_at'] > last_run]

# 3. For each news item:
for item in new_news:
    # Fetch full article
    html = fetch(item['link'])
    
    # LLM summarize with category-specific prompt
    summary = llm_call(html, category=item['category'])
    
    # Build embed
    embed = build_gamer_embed(summary, item)
    
    # Post to Discord
    post_webhook(embed, mention=role_ids[item['category']])

# 4. Tier changes
snapshot = load("heroes_snapshot.json")
current = load("heroes.json")
changes = compare_tiers(snapshot, current)
if changes:
    embed = build_tier_embed(changes)
    post_webhook(embed, mention=role_ids['meta'])

# 5. Meta overview
meta = llm_analyze_meta(new_news, videos_7d, changes)
embed = build_meta_embed(meta)
post_webhook(embed, mention=role_ids['meta'])

# 6. Save timestamp
save_last_run_timestamp()
```

### LLM Integration

**Endpoint:** 9router (OpenAI-compatible)
```python
response = openai.ChatCompletion.create(
    model=config['llm_model'],
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": article_text}
    ],
    temperature=0.7,
    max_tokens=1000
)
```

**System Prompt (example for patch notes):**
```
Bạn là chuyên gia Liên Quân Mobile. Phân tích patch notes và trích xuất:
1. Tướng nào bị buff/nerf với số liệu cụ thể (trước → sau, % thay đổi)
2. Items thay đổi
3. Meta impact (tướng nào lên/xuống tier)
4. Verdict ngắn gọn cho mỗi tướng

Format: Markdown với stats rõ ràng, dễ đọc.
```

### GitHub Secrets

```
DISCORD_WEBHOOK_URL
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
```

### Discord Roles Setup

User cần tạo roles trong server:
```
@Patch-Notes    (color: #ff6b6b)
@Esports        (color: #4ecdc4)
@Skin-Mới       (color: #ffe66d)
@Sự-Kiện       (color: #95e1d3)
@Tướng-Mới      (color: #f38181)
@Meta-Analysis  (color: #aa96da)
```

Lưu role IDs vào `digest_config.json`.

## Data Flow

```
news_crawler.py
  └─> public/news.json (tin mới với image_url)

update_hero_trends.py
  └─> public/heroes.json (tier mới, hot_count, tier_reason)

discord_digest.py
  ├─ Đọc news.json + heroes.json + heroes_snapshot.json
  ├─ Fetch full article HTML
  ├─ LLM summarize + analyze
  ├─ Build Discord embeds
  └─ POST webhook → #lienquan-updates
```

## Error Handling

- **LLM timeout/fail:** Fallback to simple title + summary (không AI)
- **Webhook fail:** Retry 3 lần, log error
- **Article fetch fail:** Skip article, log warning
- **JSON parse error:** Skip corrupted data, use fallback

## Testing

**Local test:**
```bash
python crawler/discord_digest.py --dry-run
```

**GitHub Actions test:**
Trigger manual workflow dispatch.

## Future Enhancements

- **Multi-language support:** Detect language → translate to VI
- **Image generation:** Create meta overview graphics
- **Interactive bot:** Slash commands for user queries (requires bot token)
- **Analytics:** Track embed views, reactions, engagement

## Success Criteria

- [ ] Post news digest within 5 phút sau cron trigger
- [ ] AI tóm tắt accuracy > 90% (manual check 10 posts)
- [ ] Tier changes detection đúng 100%
- [ ] Embed render đẹp trên Discord mobile + desktop
- [ ] Zero downtime (retry logic works)
