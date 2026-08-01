# AOV Discord Digest Bot

AI-powered Discord bot tự động post tin tức Liên Quân Mobile với tóm tắt chi tiết, tier changes, meta analysis.

## Features

- 📰 **Per-news AI digest** — Mỗi tin tức = 1 embed chi tiết với stats, verdict, tier predictions
- 📊 **Tier changes detection** — So sánh snapshot trước/sau để detect buff/nerf
- 🎮 **Gamer-style embeds** — Box characters, emoji color coding, clear stats
- ✅ **No duplicates** — Tracks sent news by ID, never posts the same article twice
- 🆕 **First run: 5 newest** — Initial setup posts top 5 articles, then only new ones

## Setup

### 1. Discord Webhook

1. Server Settings → Integrations → Webhooks → New Webhook
2. Channel: `#lienquan-updates`
3. Copy webhook URL

### 2. Discord Roles (Optional)

Bot không mention roles mặc định. Nếu muốn notification theo category, thêm role mentions vào code.

### 3. LLM API (9router)

Setup 9router endpoint (OpenAI-compatible).

### 4. GitHub Secrets

Add to repo Settings → Secrets and variables → Actions:

```
DISCORD_WEBHOOK_URL
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
```

### 5. Feeds Config

Copy `public/feeds.json` and `public/news_feeds.json` from your lienquan-hub repo.

## Schedule

Runs daily at 07:00 GMT+7 (00:00 UTC).

Manual trigger: Actions tab → Discord Digest Bot → Run workflow.

## Categories

| Category | Template | Example |
|----------|----------|---------|
| Patch Notes | Stats table, buff/nerf boxes | "Điều chỉnh giữa mùa PB..." |
| Esports | Match results, MVP | "APL 2026: SGP vs VGM" |
| Skin | Info box, effects breakdown | "Skin S-tier Nakroth Huyết Nguyệt" |
| Sự Kiện | Timeline, prizes | "Đại tiệc cosplay mùa 3" |
| Tướng Mới | Skills, counters, build | "Azzenka - Pháp sư cát" |
| Meta Analysis | Tier changes, trends | "Tier changes tháng 8" |

## Local Testing

```bash
# Set env vars
export DISCORD_WEBHOOK_URL="your-webhook-url"
export LLM_BASE_URL="your-9router-endpoint"
export LLM_API_KEY="your-api-key"
export LLM_MODEL="gpt-4o-mini"

# First run: posts 5 newest articles
python crawler/discord_digest.py

# Subsequent runs: only posts new articles
python crawler/discord_digest.py
```

**Tracking:** Bot lưu `.sent_news.json` để track articles đã gửi. Xóa file này để reset (sẽ post lại 5 tin mới nhất).

## Architecture

```
GitHub Actions (07:00 GMT+7)
├─ 1. hero_snapshot.py — Save heroes.json state
├─ 2. news_crawler.py — Fetch new articles
├─ 3. youtube_rss_fetcher.py — Fetch new videos
├─ 4. update_hero_trends.py — Calculate tiers
├─ 5. discord_digest.py — LLM summarize → post Discord
└─ 6. git commit + push — Save data
```

## License

MIT
