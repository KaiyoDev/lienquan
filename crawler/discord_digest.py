#!/usr/bin/env python3
"""
Discord Digest Bot — AI-powered AOV news updates.
Posts per-news digests + tier changes + meta analysis to Discord.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(BASE_DIR, "..", "public")
NEWS_PATH = os.path.join(PUBLIC_DIR, "news.json")
HEROES_PATH = os.path.join(PUBLIC_DIR, "heroes.json")
SNAPSHOT_PATH = os.path.join(PUBLIC_DIR, "heroes_snapshot.json")
CONFIG_PATH = os.path.join(BASE_DIR, "digest_config.json")
LAST_RUN_PATH = os.path.join(BASE_DIR, ".last_run.txt")

# Category to role mapping
CATEGORY_TO_ROLE = {
    "cập nhật": "patch_notes",
    "patch": "patch_notes",
    "esports": "esports",
    "giải đấu": "esports",
    "skin": "skin",
    "trang phục": "skin",
    "sự kiện": "event",
    "event": "event",
    "tướng": "new_hero",
    "tướng mới": "new_hero",
    "meta": "meta",
    "tin tức": "meta"
}

# Embed colors
EMBED_COLORS = {
    "patch_notes": 0xff6b6b,
    "esports": 0x4ecdc4,
    "skin": 0xffe66d,
    "event": 0x95e1d3,
    "new_hero": 0xf38181,
    "meta": 0xaa96da
}

def load_config():
    """Load config from digest_config.json or environment variables"""
    config = {}

    # Try file first
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)

    # Override with env vars (GitHub Secrets)
    if os.getenv('DISCORD_WEBHOOK_URL'):
        config.setdefault('discord', {})['webhook_url'] = os.getenv('DISCORD_WEBHOOK_URL')

    if os.getenv('LLM_BASE_URL'):
        config.setdefault('llm', {})['base_url'] = os.getenv('LLM_BASE_URL')

    if os.getenv('LLM_API_KEY'):
        config.setdefault('llm', {})['api_key'] = os.getenv('LLM_API_KEY')

    if os.getenv('LLM_MODEL'):
        config.setdefault('llm', {})['model'] = os.getenv('LLM_MODEL')

    # Role IDs from env
    discord_config = config.setdefault('discord', {})
    role_ids = discord_config.setdefault('role_ids', {})

    for role in ['patch_notes', 'esports', 'skin', 'event', 'new_hero', 'meta']:
        env_key = f'DISCORD_ROLE_{role.upper()}'
        if os.getenv(env_key):
            role_ids[role] = os.getenv(env_key)

    return config

def load_json(path):
    """Load JSON file safely"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return {}

def save_last_run_timestamp():
    """Save current timestamp for next run comparison"""
    now = datetime.now(timezone.utc).isoformat()
    with open(LAST_RUN_PATH, 'w') as f:
        f.write(now)

def get_last_run_timestamp():
    """Get last run timestamp"""
    if not os.path.exists(LAST_RUN_PATH):
        # Default to 24 hours ago
        return (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with open(LAST_RUN_PATH, 'r') as f:
        return f.read().strip()

def fetch_article_html(url):
    """Fetch full article HTML"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        res = requests.get(url, headers=headers, timeout=10)
        res.encoding = 'utf-8'
        return res.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_article_content(html):
    """Extract main content from article HTML"""
    soup = BeautifulSoup(html, 'lxml')

    # Remove scripts, styles, navs
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
        tag.decompose()

    # Try common article selectors
    article = (
        soup.find('article') or
        soup.find(class_='entry-content') or
        soup.find(class_='post-content') or
        soup.find(class_='article-body') or
        soup.find(id='main-content')
    )

    if article:
        return article.get_text(separator='\n', strip=True)

    # Fallback to body
    body = soup.find('body')
    return body.get_text(separator='\n', strip=True) if body else ""

def llm_summarize(config, article_text, category):
    """Call LLM to summarize article"""
    llm_config = config.get('llm', {})
    base_url = llm_config.get('base_url')
    api_key = llm_config.get('api_key', '')
    model = llm_config.get('model', 'gpt-4o-mini')

    if not base_url:
        print("Warning: LLM not configured. Using fallback summary.")
        return article_text[:500]

    # Category-specific system prompts
    prompts = {
        "patch_notes": """Bạn là chuyên gia Liên Quân Mobile. Phân tích patch notes và trích xuất:
1. Tướng nào bị buff/nerf với số liệu CỤ THỂ (damage trước → sau, % thay đổi)
2. Chiêu thức thay đổi (cooldown, hiệu ứng)
3. Items thay đổi (stats, giá)
4. Meta impact: tướng nào lên/xuống tier, tại sao
5. Verdict ngắn gọn cho mỗi tướng (1 dòng)

Format: Markdown với stats rõ ràng, dùng ⬆️⬇️ cho buff/nerf.""",

        "esports": """Bạn là bình luận viên esports Liên Quân Mobile. Phân tích trận đấu:
1. Kết quả (team thắng, tỷ số)
2. MVP + KDA
3. Tướng pick/ban quan trọng
4. Highlights (plays nổi bật)
5. Tier impact: tướng nào mạnh/yếu từ trận này

Format: Markdown, ngắn gọn, excitement cao.""",

        "skin": """Bạn là reviewer skin Liên Quân Mobile. Đánh giá skin mới:
1. Thông tin (tên, loại, giá, ngày ra mắt)
2. Hiệu ứng từng chiêu (mô tả chi tiết)
3. Voice lines (nếu có)
4. Pros/Cons
5. Verdict: đáng mua không, cho ai

Format: Markdown với pros/cons rõ ràng.""",

        "event": """Bạn là event planner Liên Quân Mobile. Tóm tắt sự kiện:
1. Thời gian (bắt đầu, kết thúc, các mốc)
2. Giải thưởng (chi tiết từng giải)
3. Cách tham gia (step-by-step)
4. Quy định quan trọng
5. Tips để tối ưu phần thưởng

Format: Markdown với timeline rõ ràng.""",

        "new_hero": """Bạn là pro player Liên Quân Mobile. Phân tích tướng mới:
1. Stats cơ bản (máu, damage, role)
2. Bộ kỹ năng chi tiết (damage numbers, cooldown, hiệu ứng)
3. Combo cơ bản + nâng cao
4. Counters (tướng khắc chế)
5. Synergies (tướng phối hợp tốt)
6. Build khuyên dùng (items, ngọc, phép bổ trợ)
7. Tier dự đoán

Format: Markdown với stats cụ thể.""",

        "meta": """Bạn là analyst Liên Quân Mobile. Phân tích tin tức:
1. Tóm tắt nội dung chính (2-3 dòng)
2. Impact đến meta (nếu có)
3. Tướng nào bị ảnh hưởng
4. Action items (người chơi nên làm gì)

Format: Markdown ngắn gọn."""
    }

    system_prompt = prompts.get(category, prompts["meta"])

    try:
        # OpenAI-compatible API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}' if api_key else ''
        }

        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': f"Phân tích bài viết này:\n\n{article_text[:8000]}"}
            ],
            'temperature': 0.7,
            'max_tokens': 1500
        }

        # Remove empty auth header
        if not api_key:
            del headers['Authorization']

        res = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        if res.status_code == 200:
            data = res.json()
            return data['choices'][0]['message']['content']
        else:
            print(f"LLM error {res.status_code}: {res.text}")
            return article_text[:500]

    except Exception as e:
        print(f"LLM error: {e}")
        return article_text[:500]

def build_embed(news_item, summary, role_id):
    """Build Discord embed for news item"""
    category = news_item.get('category', 'tin tức')
    role_key = CATEGORY_TO_ROLE.get(category, 'meta')
    color = EMBED_COLORS.get(role_key, 0x7289da)

    # Build embed
    embed = {
        'title': f"📰 {news_item['title']}",
        'description': summary,
        'color': color,
        'timestamp': news_item.get('published_at', datetime.now(timezone.utc).isoformat()),
        'footer': {
            'text': f"{news_item.get('source', 'Liên Quân Hub')} • #{category}"
        }
    }

    # Add image
    if news_item.get('image_url'):
        embed['image'] = {'url': news_item['image_url']}

    # Add link button
    if news_item.get('link'):
        embed['url'] = news_item['link']

    # Mention role
    content = f"<@&{role_id}>" if role_id else ""

    return {'embeds': [embed], 'content': content}

def post_to_discord(webhook_url, payload):
    """Post payload to Discord webhook"""
    try:
        res = requests.post(webhook_url, json=payload, timeout=10)
        if res.status_code in [200, 204]:
            print(f"✅ Posted to Discord: {payload['embeds'][0]['title'][:50]}...")
            return True
        else:
            print(f"❌ Discord error {res.status_code}: {res.text}")
            return False
    except Exception as e:
        print(f"❌ Discord post error: {e}")
        return False

def compare_tiers():
    """Compare heroes_snapshot.json vs heroes.json to detect tier changes"""
    snapshot = load_json(SNAPSHOT_PATH)
    current = load_json(HEROES_PATH)

    if not snapshot or not current:
        return []

    snapshot_heroes = {h['id']: h for h in snapshot.get('heroes', [])}
    current_heroes = {h['id']: h for h in current.get('heroes', [])}

    changes = []

    for hero_id, current_hero in current_heroes.items():
        if hero_id not in snapshot_heroes:
            continue

        old_tier = snapshot_heroes[hero_id].get('tier', 'B')
        new_tier = current_hero.get('tier', 'B')

        if old_tier != new_tier:
            # Determine if buff or nerf
            tier_rank = {'S': 4, 'A': 3, 'B': 2, 'C': 1}
            old_rank = tier_rank.get(old_tier, 2)
            new_rank = tier_rank.get(new_tier, 2)

            change_type = 'buff' if new_rank > old_rank else 'nerf'

            changes.append({
                'id': hero_id,
                'name': current_hero['name'],
                'old_tier': old_tier,
                'new_tier': new_tier,
                'type': change_type,
                'reason': current_hero.get('tier_reason', ''),
                'thumbnail': current_hero.get('thumbnail')
            })

    return changes

def build_tier_embed(changes, config):
    """Build embed for tier changes"""
    role_id = config.get('discord', {}).get('role_ids', {}).get('meta', '')

    buffs = [c for c in changes if c['type'] == 'buff']
    nerfs = [c for c in changes if c['type'] == 'nerf']

    description = "```\n"

    if buffs:
        description += "🟢 BUFFED\n"
        for c in buffs[:5]:
            description += f"• {c['name']}: {c['old_tier']} → {c['new_tier']}\n"
            description += f"  {c['reason']}\n"

    if nerfs:
        description += "\n🔴 NERFED\n"
        for c in nerfs[:5]:
            description += f"• {c['name']}: {c['old_tier']} → {c['new_tier']}\n"
            description += f"  {c['reason']}\n"

    description += "```"

    embed = {
        'title': '📊 TIER CHANGES',
        'description': description,
        'color': EMBED_COLORS['meta'],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    # Add thumbnail of first buffed hero
    if buffs and buffs[0].get('thumbnail'):
        embed['thumbnail'] = {'url': buffs[0]['thumbnail']}

    content = f"<@&{role_id}>" if role_id else ""

    return {'embeds': [embed], 'content': content}

def main():
    print("=== DISCORD DIGEST BOT ===")

    # Load config
    config = load_config()
    webhook_url = config.get('discord', {}).get('webhook_url')

    if not webhook_url or webhook_url == 'YOUR_DISCORD_WEBHOOK_URL_HERE':
        print("Error: Discord webhook not configured.")
        sys.exit(1)

    # Get last run timestamp
    last_run = get_last_run_timestamp()
    print(f"Last run: {last_run}")

    # Load news
    news_data = load_json(NEWS_PATH)
    all_news = news_data.get('news', [])

    # Filter new news
    new_news = []
    for item in all_news:
        crawled_at = item.get('crawled_at', '')
        if crawled_at > last_run:
            new_news.append(item)

    print(f"Found {len(new_news)} new articles")

    # Process each news item
    for news_item in new_news[:10]:  # Limit to 10 per run
        print(f"\nProcessing: {news_item['title'][:60]}...")

        # Fetch full article
        html = fetch_article_html(news_item['link'])
        if not html:
            continue

        # Extract content
        article_text = extract_article_content(html)
        if not article_text:
            continue

        # LLM summarize
        category = news_item.get('category', 'tin tức')
        summary = llm_summarize(config, article_text, category)

        # Build embed
        role_key = CATEGORY_TO_ROLE.get(category, 'meta')
        role_id = config.get('discord', {}).get('role_ids', {}).get(role_key, '')
        payload = build_embed(news_item, summary, role_id)

        # Post to Discord
        post_to_discord(webhook_url, payload)

        # Rate limit
        time.sleep(2)

    # Tier changes
    print("\n=== CHECKING TIER CHANGES ===")
    tier_changes = compare_tiers()

    if tier_changes:
        print(f"Found {len(tier_changes)} tier changes")
        payload = build_tier_embed(tier_changes, config)
        post_to_discord(webhook_url, payload)
    else:
        print("No tier changes detected")

    # Save timestamp
    save_last_run_timestamp()
    print("\n=== DIGEST COMPLETED ===")

if __name__ == '__main__':
    main()
