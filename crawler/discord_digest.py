#!/usr/bin/env python3
"""
Discord Digest Bot — AI-powered AOV news updates.
Tracks sent news by ID to avoid duplicates.
First run: posts 5 newest articles.
Subsequent runs: only posts new articles since last run.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "..", "public")
NEWS_PATH = os.path.join(PUBLIC_DIR, "news.json")
SENT_NEWS_PATH = os.path.join(BASE_DIR, ".sent_news.json")

# Embed colors by category keyword
CATEGORY_COLORS = {
    "cập nhật": 0xff6b6b, "patch": 0xff6b6b,
    "esports": 0x4ecdc4, "giải đấu": 0x4ecdc4,
    "skin": 0xffe66d, "trang phục": 0xffe66d,
    "sự kiện": 0x95e1d3, "event": 0x95e1d3,
    "tướng": 0xf38181, "tướng mới": 0xf38181,
    "meta": 0xaa96da, "tin tức": 0xaa96da,
}

# LLM prompts by category
LLM_PROMPTS = {
    "patch_notes": """Viết game news cho Liên Quân Mobile patch notes.

QUAN TRỌNG:
- Nếu KHÔNG có buff/nerf tướng, nói rõ và tóm tắt nội dung thực
- KHÔNG bịa stats, KHÔNG hallucinate
- Chỉ dùng thông tin CÓ THỰC trong bài

Nếu có patch notes buff/nerf:
- Liệt kê từng tướng bị thay đổi
- Stats: cũ → mới + % thay đổi
- Dùng ⬆️⬇️ cho buff/nerf
- Giải thích impact ngắn gọn
- Meta prediction (nếu có)

FORMAT:
- Tiêu đề mỗi tướng: 🔴/🟢 [TÊN] - [Vai trò]
- Bullet points cho stats
- Ngôn ngữ gamer, ngắn gọn
- Max 1500 từ

Ví dụ:
🔴 NAKROTH - Assassin
• Chiêu 3 (Ulti):
  - Sát thương: 180 → 160 (⬇️ -11%)
  - Cooldown: 40s → 50s (⬇️ +25%)
• Impact: Burst yếu hơn, khó carry late
• Meta: S → A, switch Volkath/Murad""",

    "esports": """Viết esports news cho Liên Quân Mobile.

NỘI DUNG:
- Giải đấu, vòng đấu
- 2 đội + tỷ số
- MVP + KDA nổi bật
- Tướng pick/ban quan trọng
- Highlights (3-5 moments)
- Meta impact

FORMAT:
- 🏆 KẾT QUẢ: [Đội A] vs [Đội B] - [Tỷ số]
- ⭐ MVP: [Tên] - [KDA]
- 🔥 HIGHLIGHTS: Bullet points
- 📊 META IMPACT: Tướng nào hot/flop

Ngôn ngữ: Excitement cao, ngắn gọn, max 1200 từ.""",

    "skin": """Viết skin review cho Liên Quân Mobile.

NỘI DUNG:
- Tên skin + tướng + tier + giá
- Thiết kế tổng quan
- Hiệu ứng từng chiêu (Q/W/E/R)
- Voice lines (nếu có)
- Pros/Cons
- Verdict: đáng mua không?

FORMAT:
✨ [TÊN SKIN] - [Tướng] - [Tier]
💰 Giá: [X Quân Huy]

🎨 THIẾT KẾ:
[Mô tả ngắn]

⚡ HIỆU ỨNG:
• Chiêu 1: [Mô tả]
• Chiêu 2: [Mô tả]
• Chiêu 3: [Mô tả]
• Ulti: [Mô tả]

✅ PROS: [Bullet points]
❌ CONS: [Bullet points]

🎯 VERDICT: [X/10] - [Đáng mua cho ai?]

Ngôn ngữ: Reviewer style, max 1000 từ.""",

    "event": """Viết event guide cho Liên Quân Mobile.

NỘI DUNG:
- Tên sự kiện + thời gian
- Phần thưởng chính
- Cách tham gia (steps)
- Tips tối ưu
- Lưu ý quan trọng

FORMAT:
🎉 [TÊN SỰ KIỆN]

📅 THỜI GIAN: [Bắt đầu] → [Kết thúc]

🎁 PHẦN THƯỞNG:
• [Reward 1]
• [Reward 2]
• [Reward 3]

📝 CÁCH THAM GIA:
1. [Bước 1]
2. [Bước 2]
3. [Bước 3]

💡 TIPS:
• [Tip 1]
• [Tip 2]

⚠️ LƯU Ý:
• [Note 1]
• [Note 2]

Ngôn ngữ: Hướng dẫn rõ ràng, dễ hiểu, max 1000 từ.""",

    "new_hero": """Viết hero guide cho Liên Quân Mobile.

NỘI DUNG:
- Tên tướng + vai trò + lane
- Độ khó
- Bộ kỹ năng (Passive + 4 chiêu)
- Combo cơ bản
- Counters + Synergies
- Build khuyên dùng
- Tier prediction

FORMAT:
⚔️ [TÊN TƯỚNG] - [Vai trò] - [Lane]

📊 THÔNG TIN:
• Độ khó: ⭐⭐⭐ (3/5)
• Giá: [X Vàng/Quân Huy]

🎯 BỘ KỸ NĂNG:
• Nội tại: [Mô tả ngắn]
• Chiêu 1: [Mô tả ngắn]
• Chiêu 2: [Mô tả ngắn]
• Chiêu 3: [Mô tả ngắn]
• Ulti: [Mô tả ngắn]

💥 COMBOS:
• Basic: [Chiêu 1] → [Chiêu 2] → [Ulti]
• Advanced: [Mô tả]

🛡️ COUNTERS: [Tướng 1], [Tướng 2], [Tướng 3]
🤝 SYNERGIES: [Tướng 1], [Tướng 2], [Tướng 3]

🔧 BUILD:
• Ngọc: [Mô tả]
• Items: [List 6 items]
• Phép bổ trợ: [Tên]

📈 TIER: [S/A/B/C] - [Lý do]

Ngôn ngữ: Pro player guide, max 1200 từ.""",

    "meta": """Viết meta analysis cho Liên Quân Mobile.

NỘI DUNG:
- Tóm tắt tin tức
- Impact đến meta
- Tướng bị ảnh hưởng
- Action items cho player
- Predictions

FORMAT:
📊 [TIÊU ĐỀ TIN TỨC]

📰 TÓM TẮT:
[2-3 câu tóm tắt]

🎯 META IMPACT:
• Tướng tăng: [List + lý do]
• Tướng giảm: [List + lý do]
• Chiến thuật: [Ảnh hưởng]

💡 ACTION ITEMS:
• Ngay: [Làm gì]
• Tuần này: [Làm gì]
• Tháng này: [Làm gì]

🔮 PREDICTIONS:
• Meta sẽ: [Thay đổi thế nào]
• Chuẩn bị: [Nên làm gì]

Ngôn ngữ: Analyst style, ngắn gọn, max 1000 từ.""",

    "general": """Viết game news cho Liên Quân Mobile.

NỘI DUNG:
- Tiêu đề + tóm tắt
- Chi tiết chính (3-5 points)
- Impact/ý nghĩa
- Action (nếu có)

FORMAT:
📰 [TIÊU ĐỀ]

📝 TÓM TẮT:
[2-3 câu]

🔍 CHI TIẾT:
• [Point 1]
• [Point 2]
• [Point 3]

💡 Ý NGHĨA:
[Ảnh hưởng đến ai, nên làm gì]

Ngôn ngữ: News style, engaging, max 800 từ."""
}


def load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return {}


def load_sent_ids():
    """Load set of already-sent news IDs"""
    data = load_json(SENT_NEWS_PATH)
    return set(data.get('sent_ids', []))


def save_sent_ids(sent_ids):
    """Save sent news IDs"""
    with open(SENT_NEWS_PATH, 'w', encoding='utf-8') as f:
        json.dump({'sent_ids': list(sent_ids)}, f)


def fetch_article_html(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        return res.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def extract_article_content(html):
    soup = BeautifulSoup(html, 'lxml')
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
        tag.decompose()

    article = (
        soup.find('article') or
        soup.find(class_='entry-content') or
        soup.find(class_='post-content') or
        soup.find(class_='article-body') or
        soup.find(id='main-content')
    )
    if article:
        return article.get_text(separator='\n', strip=True)

    body = soup.find('body')
    return body.get_text(separator='\n', strip=True) if body else ""


def get_llm_prompt(category):
    """Map news category to LLM prompt key"""
    mapping = {
        "cập nhật": "patch_notes", "patch": "patch_notes",
        "esports": "esports", "giải đấu": "esports",
        "skin": "skin", "trang phục": "skin",
        "sự kiện": "event", "event": "event",
        "tướng": "new_hero", "tướng mới": "new_hero",
    }
    key = mapping.get(category, "meta")
    return LLM_PROMPTS[key]


def get_embed_color(category):
    return CATEGORY_COLORS.get(category, 0x7289da)


def llm_summarize(article_text, category):
    """Call LLM to summarize article"""
    base_url = os.getenv('LLM_BASE_URL')
    api_key = os.getenv('LLM_API_KEY', '')
    model = os.getenv('LLM_MODEL', 'gpt-4o-mini')

    if not base_url:
        print("Warning: LLM not configured. Using fallback summary.")
        return article_text[:500]

    system_prompt = get_llm_prompt(category)

    try:
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': f"Phân tích bài viết này:\n\n{article_text[:8000]}"}
            ],
            'temperature': 0.7,
            'max_tokens': 2000,
            'stream': False
        }

        res = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=120)

        if res.status_code == 200:
            data = res.json()
            return data['choices'][0]['message']['content']
        else:
            print(f"LLM error {res.status_code}: {res.text}")
            return article_text[:500]

    except Exception as e:
        print(f"LLM error: {e}")
        return article_text[:500]


def build_embed(news_item, summary):
    """Build Discord embed — no role mentions"""
    category = news_item.get('category', 'tin tức')
    color = get_embed_color(category)

    # Discord limit: description max 4096 chars
    if len(summary) > 4000:
        summary = summary[:4000] + "..."

    embed = {
        'title': f"📰 {news_item['title']}",
        'description': summary,
        'color': color,
        'timestamp': news_item.get('published_at', datetime.now(timezone.utc).isoformat()),
        'footer': {
            'text': f"{news_item.get('source', 'Liên Quân Hub')} • #{category}"
        }
    }

    if news_item.get('image_url'):
        embed['image'] = {'url': news_item['image_url']}

    if news_item.get('link'):
        embed['url'] = news_item['link']

    return {'embeds': [embed]}


def post_to_discord(webhook_url, payload):
    try:
        res = requests.post(webhook_url, json=payload, timeout=10)
        if res.status_code in [200, 204]:
            title = payload['embeds'][0].get('title', '')[:50]
            print(f"✅ Posted: {title}...")
            return True
        else:
            print(f"❌ Discord error {res.status_code}: {res.text}")
            return False
    except Exception as e:
        print(f"❌ Discord post error: {e}")
        return False


def main():
    print("=== DISCORD DIGEST BOT ===")

    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print("Error: DISCORD_WEBHOOK_URL not set.")
        sys.exit(1)

    # Load news
    news_data = load_json(NEWS_PATH)
    all_news = news_data.get('news', [])

    if not all_news:
        print("No news found. Run news_crawler.py first.")
        sys.exit(0)

    # Sort by published_at descending (newest first)
    all_news.sort(key=lambda x: x.get('published_at', ''), reverse=True)

    # Load sent IDs
    sent_ids = load_sent_ids()
    is_first_run = len(sent_ids) == 0

    if is_first_run:
        # First run: post 5 newest
        print("🆕 First run — posting 5 newest articles")
        to_post = all_news[:5]
    else:
        # Subsequent runs: only unsent news
        to_post = [n for n in all_news if n.get('id') not in sent_ids]
        print(f"Found {len(to_post)} new unsent articles (total tracked: {len(sent_ids)})")

    if not to_post:
        print("No new articles to post.")
        print("=== DIGEST COMPLETED ===")
        return

    # Post each news item
    posted_count = 0
    for news_item in to_post:
        news_id = news_item.get('id')
        if not news_id:
            continue

        # Double-check: skip if already sent
        if news_id in sent_ids:
            continue

        print(f"\nProcessing: {news_item['title'][:60]}...")

        # Fetch full article
        html = fetch_article_html(news_item['link'])
        if not html:
            print(f"⚠️ Could not fetch article, skipping")
            continue

        # Extract content
        article_text = extract_article_content(html)
        if not article_text:
            print(f"⚠️ Could not extract content, skipping")
            continue

        # LLM summarize
        category = news_item.get('category', 'tin tức')
        summary = llm_summarize(article_text, category)

        # Build & post embed
        payload = build_embed(news_item, summary)
        success = post_to_discord(webhook_url, payload)

        if success:
            sent_ids.add(news_id)
            posted_count += 1
            # Save after each post (crash-safe)
            save_sent_ids(sent_ids)

        # Rate limit
        time.sleep(2)

    print(f"\n📤 Posted {posted_count} articles")
    print("\n=== DIGEST COMPLETED ===")


if __name__ == '__main__':
    main()
