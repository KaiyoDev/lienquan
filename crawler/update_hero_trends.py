import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEROES_PATH = os.path.join(BASE_DIR, "..", "public", "heroes.json")
VIDEOS_PATH = os.path.join(BASE_DIR, "..", "public", "videos.json")
NEWS_PATH = os.path.join(BASE_DIR, "..", "public", "news.json")

def parse_iso_date(date_str):
    if not date_str:
        return None
    try:
        # Standard ISO format: "2026-05-18T10:00:18Z"
        return datetime.strptime(date_str.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        try:
            # Fallback for other formats
            return datetime.fromisoformat(date_str)
        except Exception:
            return None

def check_hero_in_text(hero_name, text):
    if not text:
        return False
    text_lower = text.lower()
    name_lower = hero_name.lower()
    
    # Special matches for complex names
    if name_lower == "tel'annas" or name_lower == "tel-annas":
        return "tel'annas" in text_lower or "tel-annas" in text_lower or "tel annas" in text_lower
    
    # Word boundary match using regex
    pattern = rf'\b{re.escape(name_lower)}\b'
    return bool(re.search(pattern, text_lower))

def update_trends():
    print("=== STARTING HERO TRENDS UPDATE ===")
    
    if not os.path.exists(HEROES_PATH):
        print(f"Error: {HEROES_PATH} does not exist. Run scripts/generate_heroes.py first.")
        return
        
    with open(HEROES_PATH, "r", encoding="utf-8") as f:
        heroes_data = json.load(f)
        
    videos = []
    if os.path.exists(VIDEOS_PATH):
        with open(VIDEOS_PATH, "r", encoding="utf-8") as f:
            videos = json.load(f).get("videos", [])
            
    news = []
    if os.path.exists(NEWS_PATH):
        with open(NEWS_PATH, "r", encoding="utf-8") as f:
            news = json.load(f).get("news", [])

    now = datetime.now(timezone.utc)
    
    # Get maximum date from data to avoid off-season issues if system clock is different
    max_video_date = None
    for v in videos:
        d = parse_iso_date(v.get("publishedAt"))
        if d and (not max_video_date or d > max_video_date):
            max_video_date = d
            
    reference_date = max_video_date if max_video_date else now
    print(f"Reference date for filtering: {reference_date}")
    
    seven_days_ago = reference_date - timedelta(days=7)
    fourteen_days_ago = reference_date - timedelta(days=14)
    
    # Filter lists
    recent_videos_7 = []
    recent_videos_14 = []
    for v in videos:
        d = parse_iso_date(v.get("publishedAt"))
        if d:
            if d >= seven_days_ago:
                recent_videos_7.append(v)
            if d >= fourteen_days_ago:
                recent_videos_14.append(v)
                
    recent_news_14 = []
    for n in news:
        d = parse_iso_date(n.get("publishedAt"))
        if d and d >= fourteen_days_ago:
            recent_news_14.append(n)
            
    print(f"Filtered {len(recent_videos_7)} videos in last 7 days.")
    print(f"Filtered {len(recent_videos_14)} videos in last 14 days.")
    print(f"Filtered {len(recent_news_14)} news in last 14 days.")
    
    # Keywords
    positive_keywords = ["op", "meta", "mạnh", "bá", "buff", "hot", "carry", "gánh", "hủy diệt", "bá đạo", "top 1"]
    negative_keywords = ["nerf", "yếu", "outmeta", "nên tránh", "counter dễ", "phế", "chơi ngu"]
    
    for hero in heroes_data.get("heroes", []):
        hero_name = hero["name"]
        
        # A. Calculate Hot Count (7 days)
        hot_count = 0
        for v in recent_videos_7:
            title = v.get("title", "")
            if check_hero_in_text(hero_name, title):
                hot_count += 1
                
        hero["hot_count"] = hot_count
        hero["hot"] = hot_count >= 3
        
        # B. Auto Tier (14 days)
        pos_count = 0
        neg_count = 0
        total_occurrences = 0
        
        # Scan 14 days videos
        for v in recent_videos_14:
            title = v.get("title", "")
            if check_hero_in_text(hero_name, title):
                total_occurrences += 1
                title_lower = title.lower()
                if any(kw in title_lower for kw in positive_keywords):
                    pos_count += 1
                if any(kw in title_lower for kw in negative_keywords):
                    neg_count += 1
                    
        # Scan 14 days news
        for n in recent_news_14:
            title = n.get("title", "")
            desc = n.get("description", "")
            if check_hero_in_text(hero_name, title) or check_hero_in_text(hero_name, desc):
                total_occurrences += 1
                text_lower = f"{title} {desc}".lower()
                if any(kw in text_lower for kw in positive_keywords):
                    pos_count += 1
                if any(kw in text_lower for kw in negative_keywords):
                    neg_count += 1
                    
        score = pos_count - neg_count
        
        # Seed tier data for low data heroes (hot_count < 2)
        s_seed_lower = {name.lower() for name in ["Volkath", "Taara", "Marja", "Violet", "Hayate", "Gildur", "Sinestrea", "Lorion"]}
        a_seed_lower = {name.lower() for name in ["Florentino", "Yena", "Murad", "Nakroth", "Keera", "Zata", "Toro"]}
        
        old_tier = hero.get("tier", "A")
        
        # Determine tier based on logic
        if hot_count >= 2:
            if score >= 3:
                tier = "S"
            elif score >= 1:
                tier = "A"
            elif score >= 0:
                tier = "B"
            else:
                tier = "C"
            tier_reason = f"Xuất hiện nhiều trong video/tin tức (Hot Count: {hot_count}, Score: {score})"
        else:
            hero_name_lower = hero_name.lower()
            if hero_name_lower in s_seed_lower:
                tier = "S"
                tier_reason = f"Được gán từ dữ liệu hạt giống (Seed S-Tier) do ít video mới (Hot Count: {hot_count})"
            elif hero_name_lower in a_seed_lower:
                tier = "A"
                tier_reason = f"Được gán từ dữ liệu hạt giống (Seed A-Tier) do ít video mới (Hot Count: {hot_count})"
            else:
                if score >= 3:
                    tier = "S"
                elif score >= 1:
                    tier = "A"
                elif score >= 0:
                    tier = "B"
                else:
                    tier = "C"
                tier_reason = f"Xuất hiện {total_occurrences} lần trong video/tin tức 14 ngày qua (Score: {score})"
            
        hero["tier"] = tier
        hero["tier_reason"] = tier_reason
        
        # C. Related Videos (max 6)
        related_videos = []
        for v in videos:
            if check_hero_in_text(hero_name, v.get("title", "")):
                related_videos.append(v.get("videoId"))
                if len(related_videos) == 6:
                    break
        hero["related_videos"] = related_videos
        
        # D. Update Dynamic Thumbnail from first video only if it is not already an official Wiki image
        current_thumb = hero.get("thumbnail")
        is_wiki_image = current_thumb and "static.wikia.nocookie.net" in current_thumb
        
        if not is_wiki_image:
            if len(related_videos) > 0:
                hero["thumbnail"] = f"https://img.youtube.com/vi/{related_videos[0]}/maxresdefault.jpg"
            else:
                hero["thumbnail"] = None
        
        if hot_count > 0 or tier != "A":
            print(f"Updated {hero_name}: Hot Count={hot_count}, Hot={hero['hot']}, Tier={tier} (was {old_tier}), Related Videos={len(related_videos)}")

    # Add updated timestamp
    heroes_data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(HEROES_PATH, "w", encoding="utf-8") as f:
        json.dump(heroes_data, f, ensure_ascii=False, indent=2)
        
    print(f"=== HERO TRENDS UPDATE COMPLETED SUCCESSFULLY! ===")

if __name__ == "__main__":
    update_trends()
