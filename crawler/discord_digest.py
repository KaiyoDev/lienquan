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
    "patch_notes": """Bạn là chuyên gia phân tích Liên Quân Mobile.

QUAN TRỌNG - ĐỌC KỸ TRƯỚC KHI TRẢ LỜI:
- Nếu bài viết KHÔNG chứa thông tin về thay đổi sức mạnh tướng (buff/nerf), NÓI RÕ: "Bài này không phải patch notes về cân bằng tướng" và tóm tắt nội dung thực tế
- TUYỆT ĐỐI KHÔNG bịa stats, KHÔNG hallucinate tướng được buff/nerf nếu không có trong bài
- Chỉ trích xuất thông tin CÓ THỰC trong bài viết

Nếu bài viết LÀ patch notes (có bảng stats thay đổi tướng):

PHÂN TÍCH CHI TIẾT TỪNG TƯỚNG:
1. Với MỖI tướng bị thay đổi:
   - Tên tướng + vai trò (Assassin/Tank/Mage/etc)
   - Loại thay đổi: 🟢 BUFF / 🔴 NERF / 🟡 ADJUST
   - Chi tiết TỪNG chiêu thức thay đổi:
     • Tên chiêu + số chiêu (Q/W/E/R hoặc 1/2/3/Ulti)
     • Stats cũ → Stats mới (sát thương, cooldown, mana cost, etc)
     • Giải thích thay đổi này ảnh hưởng thế nào đến gameplay
   - Impact tổng thể: Tướng này mạnh hơn hay yếu hơn, tại sao?
   - Meta prediction: Tier sẽ thay đổi thế nào (S→A, B→S, etc)
   - Khuyến nghị: Nên pick/ban/avoid không?

2. Items thay đổi (nếu có):
   - Tên item + stats cũ → mới
   - Ảnh hưởng đến tướng nào

3. Meta Analysis:
   - Tướng nào sẽ lên meta sau patch này
   - Tướng nào sẽ rơi khỏi meta
   - Chiến thuật/team comp nào bị ảnh hưởng

FORMAT:
- Dùng ⬆️⬇️ cho buff/nerf với % cụ thể
- Dùng box characters để tạo visual đẹp
- Giải thích bằng ngôn ngữ gamer, dễ hiểu
- Dài và chi tiết, không tóm tắt quá ngắn

Ví dụ output (CHỈ dùng khi bài viết có thực):
```
🔴 NAKROTH - Assassin/Rừng - NERF NẶNG

┌─ CHI TIẾT THAY ĐỔI ─────────────────────┐
│ Chiêu 3: Uy Áp (Ultimate)               │
│ • Sát thương: 180 (+0.8AD) → 160 (+0.7AD)│
│   ⬇️ -11% base damage, -12.5% scaling   │
│ • Cooldown: 40s → 50s                    │
│   ⬇️ +25% cooldown = 10s lâu hơn         │
│ • Thời gian miễn CC: 1.5s → 1.2s        │
│   ⬇️ -20% = dễ bị lock hơn               │
└──────────────────────────────────────────┘

💀 IMPACT:
Nakroth mất khả năng burst 1-shot và survive trong combat.
Ulti yếu hơn + CD lâu hơn = ít cơ hội carry teamfight.
Dễ bị counter hơn khi miễn CC ngắn.

📊 META PREDICTION: S → A (rơi khỏi top pick)
Khuyến nghị: Switch sang Volkath/Murad nếu main rừng.
```

Bắt đầu phân tích chi tiết:""",

    "esports": """Bạn là bình luận viên esports Liên Quân Mobile chuyên nghiệp.

PHÂN TÍCH TRẬN ĐẤU CHI TIẾT:

1. TỔNG QUAN:
   - Tên giải đấu (APL, AIC, ĐTDV, etc)
   - Vòng đấu (Bảng/Playoff/Chung kết)
   - 2 đội + logo/flag
   - Kết quả cuối cùng (tỷ số BO5/BO7)

2. DIỄN BIẾN TỪNG GAME:
   Với mỗi game:
   - Đội thắng + thời gian trận đấu
   - MVP + KDA chi tiết
   - Tướng pick quan trọng (đặc biệt nếu là meta pick hoặc surprise pick)
   - Key moments: First blood, objectives (Rồng, Caesar), teamfight quyết định
   - Highlights: Outplay, combo đẹp, steals

3. PHÂN TÍCH CHIẾN THUẬT:
   - Draft phase: Ban/pick strategy của 2 đội
   - Early game: Lane dominance, jungle control
   - Mid game: Objective control, rotations
   - Late game: Teamfight composition, win condition
   - Tướng nào hoạt động tốt/kém và tại sao

4. META IMPACT:
   - Tướng nào được chứng minh mạnh từ trận này
   - Tướng nào bị expose yếu
   - Chiến thuật mới nổi (nếu có)
   - Dự đoán tier changes sau giải

5. PREDICTIONS:
   - Đội nào sẽ vô địch
   - Tướng nào sẽ hot pick sau giải

FORMAT: Dùng emoji 🏆🔥⭐, viết như bình luận viên thực thụ, excitement cao nhưng chuyên nghiệp.""",

    "skin": """Bạn là reviewer chuyên nghiệp về skin Liên Quân Mobile.

ĐÁNH GIÁ SKIN CHI TIẾT:

1. THÔNG TIN CƠ BẢN:
   - Tên skin + tướng
   - Loại skin (Bậc, S-Tier, SS-Tier, Limited, Event exclusive)
   - Giá (Quân Huy, Vàng, Event token, etc)
   - Ngày ra mắt + thời gian bán (nếu limited)
   - Có trong bundle/gacha không?

2. THIẾT KẾ & MODEL:
   - Mô tả ngoại hình chi tiết (outfit, weapon, accessories)
   - Theme/concept (cyberpunk, fantasy, historical, etc)
   - So sánh với skin gốc và các skin khác của tướng này
   - Quality của model (detail, animation idle, v.v.)

3. HIỆU ỨNG KỸ NĂNG (quan trọng nhất):
   Với MỖI chiêu thức (Passive, Q, W, E, R):
   - Mô tả hiệu ứng visual (particles, colors, shapes)
   - So sánh với skin gốc
   - Sound effects (âm thanh khi cast, hit)
   - Có animation đặc biệt không?

4. VOICE LINES & AUDIO:
   - Voice lines đặc biệt (liệt kê 3-5 câu hay nhất)
   - Có voice line tiếng Việt không?
   - Sound design tổng thể
   - Recall animation (nếu có)

5. ANIMATIONS KHÁC:
   - Movement animation
   - Attack animation
   - Recall/Emote animations
   - Kill celebration (nếu có)

6. PROS & CONS:
   ✅ Pros: (liệt kê 4-5 điểm mạnh)
   ❌ Cons: (liệt kê 2-3 điểm yếu nếu có)

7. VERDICT:
   - Điểm đánh giá: X/10
   - Đáng mua không? Cho ai?
   - So sánh value với các skin cùng tier
   - Nếu phải chọn 1 trong 3 skin S-tier, nên chọn skin nào?

FORMAT: Dùng emoji ✨🎨💎, review như Youtuber gaming chuyên nghiệp, chi tiết và có opinion rõ ràng.""",

    "event": """Bạn là event planner chuyên nghiệp cho Liên Quân Mobile.

HƯỚNG DẪN SỰ KIỆN CHI TIẾT:

1. TỔNG QUAN SỰ KIỆN:
   - Tên sự kiện
   - Loại (Login reward, Mission, Gacha, Tournament, Cosplay contest, etc)
   - Thời gian bắt đầu - kết thúc (ngày cụ thể)
   - Đối tượng tham gia (tất cả players, ranked players, etc)

2. TIMELINE CHI TIẾT:
   - Phase 1: [Ngày] - [Hoạt động]
   - Phase 2: [Ngày] - [Hoạt động]
   - Phase 3: [Ngày] - [Hoạt động]
   (Liệt kê tất cả milestones quan trọng)

3. PHẦN THƯỞNG (chi tiết từng phần):
   Với mỗi phần thưởng:
   - Tên + hình ảnh mô tả
   - Số lượng
   - Cách nhận (login, mission, gacha, etc)
   - Giá trị ước tính (nếu có thể)
   - Độ hiếm/khó nhận

4. CÁCH THAM GIA (step-by-step):
   Bước 1: ...
   Bước 2: ...
   Bước 3: ...
   (Hướng dẫn chi tiết từ A-Z, kể cả những bước nhỏ nhất)

5. NHIỆM VỤ/YÊU CẦU (nếu có):
   - Daily missions
   - Weekly missions
   - Special challenges
   - Requirements (rank, level, etc)

6. QUY ĐỊNH QUAN TRỌNG:
   - Giới hạn số lần tham gia
   - Điều kiện đặc biệt
   - Những điều KHÔNG được làm
   - Anti-cheat rules (nếu có)

7. TIPS & STRATEGY:
   - Cách tối ưu hóa phần thưởng
   - Mẹo tiết kiệm thời gian/tiền
   - Những lỗi thường gặp và cách tránh
   - Priority: Nên tập trung vào phần thưởng nào trước

8. FAQ (nếu có thông tin):
   - Hỏi đáp những câu hỏi thường gặp

FORMAT: Dùng emoji 📅🎁✨, viết như hướng dẫn cho người mới chơi, rõ ràng và dễ follow.""",

    "new_hero": """Bạn là pro player Liên Quân Mobile, chuyên gia phân tích tướng mới.

PHÂN TÍCH TƯỚNG MỚI CHI TIẾT:

1. THÔNG TIN CƠ BẢN:
   - Tên tướng (tiếng Việt + English nếu có)
   - Vai trò chính (Assassin/Mage/Tank/Marksman/Support)
   - Vai trò phụ (nếu có)
   - Lane phù hợp (Mid/Top/Jungle/Support)
   - Độ khó: ⭐⭐⭐⭐⭐ (1-5 sao)
   - Release date + giá (Vàng/Quân Huy)

2. STATS CƠ BẢN (Level 1 → Level 15):
   - HP: X (+Y/level)
   - Mana/Energy: X (+Y/level)
   - AD: X (+Y/level)
   - AP: X (+Y/level)
   - Armor: X (+Y/level)
   - Magic Resist: X (+Y/level)
   - Attack Speed: X (+Y/level)
   - Movement Speed: X

3. BỘ KỸ NĂNG CHI TIẾT:

   🔄 Nội tại: [Tên]
   - Mô tả chi tiết
   - Số liệu cụ thể (damage, duration, etc)
   - Cách hoạt động trong combat

   1️⃣ Chiêu 1: [Tên] - CD: Xs - Mana: Y
   - Mô tả chi tiết
   - Damage: [base] + [scaling]
   - Hiệu ứng (CC, buff, debuff)
   - Tips sử dụng

   2️⃣ Chiêu 2: [Tên] - CD: Xs - Mana: Y
   - Mô tả chi tiết
   - Damage: [base] + [scaling]
   - Hiệu ứng
   - Tips sử dụng

   3️⃣ Chiêu 3: [Tên] - CD: Xs - Mana: Y
   - Mô tả chi tiết
   - Damage: [base] + [scaling]
   - Hiệu ứng
   - Tips sử dụng

   💫 Ultimate: [Tên] - CD: Xs - Mana: Y
   - Mô tả chi tiết
   - Damage: [base] + [scaling]
   - Hiệu ứng đặc biệt
   - Cách combo với chiêu khác

4. COMBOS:
   - Basic combo (dễ nhất): [Chiêu 1] → [Chiêu 2] → ...
   - Advanced combo (khó hơn): [Chiêu 2] → [Ulti] → [Chiêu 1] → ...
   - Escape combo: [Chiêu X] → [Chiêu Y]
   - One-shot combo: [Full combo để kill 1 target]

5. COUNTERS (tướng khắc chế):
   - Tướng 1: Lý do tại sao counter
   - Tướng 2: Lý do tại sao counter
   - Tướng 3: Lý do tại sao counter
   - Cách chơi khi gặp counter

6. SYNERGIES (tướng phối hợp tốt):
   - Tướng 1: Tại sao phối hợp tốt
   - Tướng 2: Tại sao phối hợp tốt
   - Tướng 3: Tại sao phối hợp tốt
   - Team comp lý tưởng

7. BUILD KHUYÊN DÙNG:

   📿 Ngọc bổ trợ:
   - Ngọc đỏ: X viên [Tên] - Lý do
   - Ngọc tím: X viên [Tên] - Lý do
   - Ngọc xanh: X viên [Tên] - Lý do

   🛡️ Trang bị (theo thứ tự):
   1. [Item 1] - Lý do
   2. [Item 2] - Lý do
   3. [Item 3] - Lý do
   4. [Item 4] - Lý do
   5. [Item 5] - Lý do
   6. [Item 6] - Lý do

   ✨ Phép bổ trợ: [Tên] - Lý do

   🎯 Emblem: [Tên] - Lý do

8. TIER DỰ ĐOÁN:
   - Tier hiện tại: S/A/B/C
   - Tier sau 1 tháng: Dự đoán
   - Lý do cho tier prediction

9. KẾT LUẬN:
   - Tướng này dành cho ai?
   - Có đáng mua không?
   - Meta prediction (sẽ hot hay niche)

FORMAT: Dùng emoji 🎯⚔️🛡️, viết như guide cho streamer, chi tiết và actionable.""",

    "meta": """Bạn là analyst chuyên nghiệp Liên Quân Mobile.

PHÂN TÍCH TIN TỨC CHI TIẾT:

1. TÓM TẮT NỘI DUNG CHÍNH:
   - Vấn đề/sự kiện chính được đề cập
   - Ai liên quan (tướng, đội tuyển, NPH, etc)
   - Khi nào xảy ra
   - Tại sao quan trọng

2. CHI TIẾT ĐẦY ĐỦ:
   - Mô tả chi tiết nội dung tin tức
   - Background/context (nếu cần)
   - Các bên liên quan nói gì/làm gì
   - Phản ứng của cộng đồng (nếu có)

3. IMPACT ĐẾN META:
   - Ảnh hưởng trực tiếp đến tướng nào?
   - Ảnh hưởng đến chiến thuật/team comp nào?
   - Ảnh hưởng đến rank/competitive play không?
   - Timeline: Khi nào impact sẽ rõ ràng?

4. TƯỚNG BỊ ẢNH HƯỞNG:
   Với mỗi tướng:
   - Tên tướng
   - Ảnh hưởng tích cực/tiêu cực
   - Lý do tại sao
   - Nên làm gì (pick/avoid/counter)

5. ACTION ITEMS (người chơi nên làm gì):
   - Immediate actions (ngay bây giờ)
   - Short-term (tuần này)
   - Long-term (tháng này)
   - Recommendations cụ thể cho từng rank

6. PREDICTIONS:
   - Điều gì sẽ xảy ra tiếp theo?
   - Meta sẽ thay đổi thế nào?
   - Nên chuẩn bị gì?

FORMAT: Dùng emoji 📊🎯💡, viết như analysis cho esports team, chuyên sâu nhưng dễ hiểu.""",

    "general": """Bạn là content creator Liên Quân Mobile chuyên nghiệp.

TÓM TẮT TIN TỨC CHI TIẾT:

1. HEADLINE:
   - Tiêu đề chính của tin tức
   - Tại sao tin này quan trọng

2. NỘI DUNG CHÍNH:
   - Mô tả chi tiết nội dung
   - Key points (3-5 điểm quan trọng nhất)
   - Background/context nếu cần

3. CHI TIẾT ĐẦY ĐỦ:
   - Tất cả thông tin từ bài viết
   - Số liệu cụ thể (nếu có)
   - Quotes/statements quan trọng
   - Hình ảnh/media được đề cập

4. Ý NGHĨA & IMPACT:
   - Tin này ảnh hưởng đến ai?
   - Người chơi nên biết gì?
   - Có cần action gì không?

5. TÓM LẠI:
   - TL;DR version (2-3 câu)
   - Key takeaway

FORMAT: Dùng emoji phù hợp với nội dung, viết engaging như Youtuber gaming, chi tiết và dễ đọc."""
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
            'max_tokens': 4000,  # Tăng output để có summary chi tiết
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
