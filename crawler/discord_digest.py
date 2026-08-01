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

STYLE: Linh hoạt, tự biến tấu tùy nội dung
- Đọc bài viết và chọn format phù hợp nhất
- Có thể dùng: ⬆️⬇️, 🔴🟢, ▼//, hoặc format khác
- KHÔNG bắt buộc theo template cứng

QUAN TRỌNG:
- Nếu KHÔNG có buff/nerf tướng, nói rõ và tóm tắt nội dung thực
- KHÔNG bịa stats, KHÔNG hallucinate
- Chỉ dùng thông tin CÓ THỰC trong bài

Nếu có patch notes buff/nerf:
- Liệt kê từng tướng bị thay đổi
- Stats: cũ → mới + % thay đổi (nếu có số liệu)
- Giải thích impact ngắn gọn
- Meta prediction (nếu có)

GỢI Ý (tham khảo, không bắt buộc):
🔴/🟢 **[TÊN TƯỚNG]** - [Vai trò]
• [Chiêu thức]: [Stat cũ] → [Stat mới]
• Impact: [Giải thích ngắn]
• Meta: [Prediction]

Ngôn ngữ: Gamer style, ngắn gọn, max 1500 từ""",

    "esports": """Viết esports news cho Liên Quân Mobile.

STYLE: Excitement cao, tự biến tấu tùy trận đấu
- Đọc bài viết và chọn format phù hợp nhất
- Có thể dùng: 🏆⭐🔥📊, hoặc emoji khác
- KHÔNG bắt buộc theo template cứng

GỢI Ý NỘI DUNG (tùy chọn):
- Giải đấu, vòng đấu
- 2 đội + tỷ số
- MVP + KDA nổi bật (nếu có)
- Tướng pick/ban quan trọng (nếu có)
- Highlights (nếu có)
- Meta impact (nếu có)

GỢI Ý FORMAT (tham khảo, không bắt buộc):
🏆 **[Giải đấu/Vòng đấu]**
**[Đội A] vs [Đội B]** - [Tỷ số]

[Section phù hợp với nội dung]

Ngôn ngữ: Excitement cao, ngắn gọn, max 1200 từ""",

    "skin": """Viết skin review cho Liên Quân Mobile.

STYLE: Reviewer style, tự biến tấu tùy skin
- Đọc bài viết và chọn format phù hợp nhất
- Có thể dùng: ✨🎨⚡✅❌🎯, hoặc emoji khác
- KHÔNG bắt buộc theo template cứng

GỢI Ý NỘI DUNG (tùy chọn):
- Tên skin + tướng + tier + giá (nếu có)
- Thiết kế tổng quan
- Hiệu ứng từng chiêu (nếu có thông tin)
- Voice lines (nếu có)
- Pros/Cons
- Verdict: đáng mua không?

GỢI Ý FORMAT (tham khảo, không bắt buộc):
✨ **[TÊN SKIN]** - [Tướng]

[Section phù hợp với nội dung]

Ngôn ngữ: Reviewer style, max 1000 từ""",

    "event": """Thông báo sự kiện Liên Quân Mobile.

STYLE: Formal, clean - biến tấu linh hoạt tùy nội dung
- Đọc bài viết và tự chọn format phù hợp nhất
- Có thể dùng: ▼//, 📅, 🎁, hoặc emoji khác tùy ngữ cảnh
- KHÔNG bắt buộc theo template cứng
- Chỉ liệt kê thông tin, KHÔNG phân tích

GỢI Ý FORMAT (tham khảo, không bắt buộc):
🎉 **[TÊN SỰ KIỆN]** [đã ra mắt/sắp diễn ra/etc]!

▼// **[Section 1]**
[Nội dung]

▼// **[Section 2]**
[Nội dung]

※ [Lưu ý nếu có]

QUAN TRỌNG:
- Tự biến tấu format cho phù hợp nội dung
- Formal tone, professional
- KHÔNG phân tích, tính toán tỷ lệ/chi phí
- Max 400 từ
"""

    "new_hero": """Viết hero guide cho Liên Quân Mobile.

STYLE: Guide style, tự biến tấu tùy tướng
- Đọc bài viết và chọn format phù hợp nhất
- Có thể dùng: ⚔️🎯💥📊🔧📈, hoặc emoji khác
- KHÔNG bắt buộc theo template cứng

GỢI Ý NỘI DUNG (tùy chọn):
- Tên tướng + vai trò + lane
- Độ khó
- Bộ kỹ năng (Passive + 4 chiêu)
- Combo cơ bản
- Counters + Synergies
- Build khuyên dùng
- Tier prediction

GỢI Ý FORMAT (tham khảo, không bắt buộc):
⚔️ **[TÊN TƯỚNG]** - [Vai trò]

[Section phù hợp với nội dung]

Ngôn ngữ: Guide style, chi tiết, max 1500 từ""",

    "meta": """Phân tích meta Liên Quân Mobile.

STYLE: Analytical, tự biến tấu tùy nội dung
- Đọc bài viết và chọn format phù hợp nhất
- Có thể dùng: 📊🟢🔴📈💡🔮, hoặc emoji khác
- KHÔNG bắt buộc theo template cứng

GỢI Ý NỘI DUNG (tùy chọn):
- Tướng nào đang mạnh/yếu
- Lý do (buff/nerf, item mới, chiến thuật)
- Meta shifts (thay đổi so với trước)
- Khuyến nghị pick/ban
- Predictions

GỢI Ý FORMAT (tham khảo, không bắt buộc):
📊 **META ANALYSIS**

[Section phù hợp với nội dung]

Ngôn ngữ: Analytical, max 1200 từ""",

    "general": """Thông báo tin tức chung cho Liên Quân Mobile.

STYLE: Casual, friendly - biến tấu linh hoạt tùy nội dung
- Đọc bài viết và tự chọn format phù hợp nhất
- Có thể dùng: 📰, 📅, 🎮, ⚡, 💡, hoặc emoji khác
- KHÔNG bắt buộc theo template cứng
- Tự quyết định cần bao nhiêu section, tên gì

GỢI Ý (tham khảo, không bắt buộc):
📰 **[TÊN TIN TỨC]**

[Mô tả ngắn]

[Section 1 - tên tùy chọn]
[Nội dung]

[Section 2 - nếu cần]
[Nội dung]

QUAN TRỌNG:
- Tự biến tấu format cho phù hợp nội dung
- Casual tone, friendly
- KHÔNG phân tích sâu
- Max 400 từ
""",

    "event_analysis": """Phân tích chi tiết sự kiện Liên Quân Mobile (reply message).

STYLE: Analytical, tự biến tấu tùy sự kiện
- Đọc bài viết và chọn format phù hợp nhất
- Có thể dùng: 📊💰🎲💡⚖️🎯, hoặc emoji khác
- KHÔNG bắt buộc theo template cứng

GỢI Ý NỘI DUNG (tùy chọn):
- Phân tích tỷ lệ/quay (nếu có số liệu)
- Tính toán chi phí ước tính (nếu có thể)
- Pity system (nếu có)
- Free pulls/cách tối ưu
- Tips cho người chơi
- So sánh với sự kiện trước (nếu biết)

GỢI Ý FORMAT (tham khảo, không bắt buộc):
📊 **PHÂN TÍCH: [TÊN SỰ KIỆN]**

[Section phù hợp với nội dung]

QUAN TRỌNG:
- Phân tích dựa trên số liệu từ bài viết
- Nếu bài viết không có số liệu, ghi rõ "Bài viết không cung cấp số liệu cụ thể"
- Max 800 từ
"""
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


def post_to_discord(webhook_url, payload, return_message_id=False):
    try:
        # Add wait_id parameter to get message object
        url = webhook_url + '?wait=true' if return_message_id else webhook_url
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code in [200, 204]:
            title = payload['embeds'][0].get('title', '')[:50]
            print(f"✅ Posted: {title}...")
            if return_message_id and res.status_code == 200:
                data = res.json()
                return data.get('id')
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
        # First run: post ALL unsent articles (backfill from July)
        print("🆕 First run — posting ALL articles from July onwards")
        to_post = all_news
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

        # Fix markdown escape
        summary = summary.replace('\\n', '\n')
        summary = summary.replace('\\*\\*', '**')
        summary = summary.replace('\\*', '*')

        # Build & post embed
        payload = build_embed(news_item, summary)

        # For events, we need message_id to reply with analysis
        is_event = category in ['sự kiện', 'event']
        result = post_to_discord(webhook_url, payload, return_message_id=is_event)

        if result:
            sent_ids.add(news_id)
            posted_count += 1
            # Save after each post (crash-safe)
            save_sent_ids(sent_ids)

            # If event, also post analysis as reply
            if is_event and isinstance(result, str):
                message_id = result
                print(f"📊 Generating event analysis reply...")

                # Generate analysis
                analysis_summary = llm_summarize(article_text, 'event_analysis')
                analysis_summary = analysis_summary.replace('\\n', '\n')
                analysis_summary = analysis_summary.replace('\\*\\*', '**')
                analysis_summary = analysis_summary.replace('\\*', '*')

                # Build analysis embed
                analysis_payload = {
                    'embeds': [{
                        'title': f"📊 Phân tích: {news_item['title']}",
                        'description': analysis_summary,
                        'color': 0x95e1d3,  # Event color
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }],
                    'message_reference': {
                        'message_id': message_id
                    }
                }

                # Post reply
                post_to_discord(webhook_url, analysis_payload)
                time.sleep(2)  # Rate limit

        # Rate limit
        time.sleep(2)

    print(f"\n📤 Posted {posted_count} articles")
    print("\n=== DIGEST COMPLETED ===")


if __name__ == '__main__':
    main()
