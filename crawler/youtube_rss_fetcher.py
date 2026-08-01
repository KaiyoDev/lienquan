import feedparser, json, re, os, time, sys, requests
try:
    from ftfy import fix_text  # Robustly fixes mojibake
except Exception:
    fix_text = None
from urllib.parse import urlparse, parse_qs

# Set UTF-8 encoding for stdout
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.join(os.path.dirname(__file__), '..')
FEEDS_PATH = os.path.join(ROOT, 'public', 'feeds.json')
OUT_PATH = os.path.join(ROOT, 'public', 'videos.json')
MAX_VIDEOS = 200


def video_id_from_link(link):
    if 'watch?v=' in link:
        return parse_qs(urlparse(link).query).get('v', [None])[0]
    m = re.search(r'youtube\.com/embed/([^/?]+)', link)
    if m:
        return m.group(1)
    m = re.search(r'youtu\.be/([^/?]+)', link)
    if m:
        return m.group(1)
    return None


def clean_and_fix_title(title):
    if not title:
        return title
    original = title
    
    # 1. Try ftfy if available
    if fix_text:
        try:
            title = fix_text(title)
        except Exception:
            pass
            
    # 2. Try common encoding fixes for mojibake (bỏ 'â' và 'Â' để tránh làm hỏng tiếng Việt chuẩn)
    encodings = ['latin1', 'cp1252']
    for enc in encodings:
        if any(bad in title for bad in ('Ã', 'â‚¬', 'â„¢', 'œ', 'áº', 'á»', 'æ', 'ë', 'ì', 'í')):
            try:
                title = title.encode(enc, errors='ignore').decode('utf-8', errors='ignore')
                break
            except Exception:
                pass
                
    # 3. Log warning if title still contains known broken patterns
    broken_patterns = ['Cm ', 'Bng ', 'LN U', 'ma bay mu']
    if any(p in title for p in broken_patterns):
        print(f"⚠️ WARNING: Title might still have encoding issues: '{title}' (Original: '{original}')")
        
    return title


def translate_title(title, source_lang='en'):
    if not title:
        return title
        
    # Check if title is purely ASCII (ignoring punctuation/numbers)
    is_ascii = all(ord(c) < 128 for c in title)
    if source_lang == 'vi' or is_ascii:
        return title
        
    # Detect language based on charsets
    lang = source_lang
    if any('\u0e00' <= c <= '\u0e7f' for c in title):
        lang = 'th'
    elif any('\u4e00' <= c <= '\u9fff' for c in title):
        lang = 'zh'
        
    print(f"Translating: '{title}' ({lang} -> vi)")
    
    # 1. Google Translate Web API (Primary - Super fast and high quality)
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={lang}&tl=vi&dt=t&q={requests.utils.quote(title)}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            translated_text = "".join([part[0] for part in data[0] if part[0]])
            if translated_text:
                print(f"-> Google Translated: '{translated_text}'")
                return translated_text
    except Exception as e:
        print(f"Google Translate error: {e}")

    # 2. MyMemory Translation API (Secondary fallback)
    try:
        url = f"https://api.mymemory.translated.net/get?q={requests.utils.quote(title)}&langpair={lang}|vi"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            translated_text = data.get('responseData', {}).get('translatedText')
            if translated_text:
                print(f"-> MyMemory Translated: '{translated_text}'")
                return translated_text
    except Exception as e:
        print(f"MyMemory Translate error: {e}")
        
    # 3. LibreTranslate instances (Tertiary fallback)
    instances = [
        "https://libretranslate.de/translate",
        "https://translate.argosopentech.com/translate",
        "https://translate.terraprint.co/translate"
    ]
    
    payload = {
        "q": title,
        "source": lang,
        "target": "vi",
        "format": "text"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    for instance in instances:
        try:
            res = requests.post(instance, json=payload, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                translated_text = data.get('translatedText')
                if translated_text:
                    time.sleep(0.3)
                    print(f"-> LibreTranslate Translated: '{translated_text}'")
                    return translated_text
        except Exception as e:
            print(f"LibreTranslate error at {instance}: {e}")
            
    # If all fail, return original
    time.sleep(0.3)
    return title


def test_encoding_fixes():
    print("=== RUNNING TITLE ENCODING TESTS ===")
    test_cases = [
        "Cm Nakroth ma bay mu Tiu Lai Bng",
        "LAI BNG QUAY RA SKIN NAKROTH LEVI NGAY T LN U",
        "Ãnh SÃ¡ng vÃ  BÃ³ng TÃ³i"
    ]
    for tc in test_cases:
        fixed = clean_and_fix_title(tc)
        print(f"Original: '{tc}' -> Fixed: '{fixed}'")
    print("====================================")


def fetch():
    # Run tests on start
    test_encoding_fixes()

    # Read feeds.json with utf-8-sig to handle BOM if present
    with open(FEEDS_PATH, 'r', encoding='utf-8-sig') as f:
        feeds = json.load(f)

    # Load existing videos for cache
    existing_videos_map = {}
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                for v in existing_data.get('videos', []):
                    existing_videos_map[v['videoId']] = v
        except Exception as e:
            print(f"Error loading existing videos for cache: {e}")

    videos = feeds.get('manual_videos', []).copy()
    print(f'Starting with {len(videos)} manual videos')

    for ch in feeds.get('channels', []):
        country = ch.get('country', 'VN')
        lang = ch.get('lang', 'vi')
        
        if ch['type'] == 'channel':
            rss = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['id']}"
        elif ch['type'] == 'playlist':
            rss = f"https://www.youtube.com/feeds/videos.xml?playlist_id={ch['id']}"
        else:
            continue

        print('Fetching', rss)
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            res = requests.get(rss, headers=headers, timeout=10)
            res.encoding = 'utf-8'
            d = feedparser.parse(res.text)
        except Exception as e:
            print(f"Failed to fetch RSS via requests: {e}. Falling back to feedparser.parse(rss)")
            d = feedparser.parse(rss)

        for entry in d.entries[:50]:
            link = entry.link
            vid = video_id_from_link(link)
            if not vid:
                continue

            # Check cache
            cached_video = existing_videos_map.get(vid)
            
            # Title processing - Luôn lấy tiêu đề sạch từ RSS mới
            raw_title = clean_and_fix_title(entry.title)
            
            title_translated = raw_title
            is_translated = False
            
            if lang != 'vi':
                # Nếu là kênh nước ngoài và đã có cache dịch, ta dùng lại bản dịch để tiết kiệm API
                if cached_video and cached_video.get('translated') is True and cached_video.get('title'):
                    title_translated = cached_video.get('title')
                    is_translated = True
                else:
                    title_translated = translate_title(raw_title, lang)
                    is_translated = (title_translated != raw_title)
            else:
                # Nếu là kênh tiếng Việt, ta luôn dùng tiêu đề sạch mới từ RSS
                title_translated = raw_title
                is_translated = False

            # Kênh trong feeds.json đã được chọn sẵn — bỏ lọc keyword (tránh mất video esports/APL)

            if len(title_translated) < 10:  # Too short
                print(f'❌ Skipping too short title: {title_translated}')
                continue
                
            if len(title_translated) > 200:  # Too long
                print(f'❌ Skipping too long title: {title_translated[:60]}...')
                continue

            # Try to extract publish date in ISO8601
            published_iso = None
            try:
                if getattr(entry, 'published_parsed', None):
                    published_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', entry.published_parsed)
                elif getattr(entry, 'updated_parsed', None):
                    published_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', entry.updated_parsed)
            except Exception:
                published_iso = None

            thumbnail_url = f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
            
            item = {
                "videoId": vid, 
                "title": title_translated, 
                "title_original": raw_title,
                "translated": is_translated,
                "country": country,
                "lang_original": lang,
                "source": "youtube", 
                "publishedAt": published_iso,
                "thumbnailUrl": thumbnail_url
            }
            existing_item = next((v for v in videos if v['videoId'] == vid), None)
            if existing_item:
                existing_item['country'] = country
                existing_item['lang_original'] = lang
                existing_item['title'] = title_translated
                existing_item['title_original'] = raw_title
                existing_item['translated'] = is_translated
            else:
                videos.append(item)
                print(f'Added video: {title_translated[:50]}... - {published_iso}')

    # Giữ video cũ nếu lần crawl này RSS lỗi hoặc lọc quá ít
    seen_ids = {v['videoId'] for v in videos if v.get('videoId')}
    preserved = 0
    for vid, cached in existing_videos_map.items():
        if vid not in seen_ids:
            videos.append(cached)
            seen_ids.add(vid)
            preserved += 1
    if preserved:
        print(f'Preserved {preserved} existing videos from previous runs')

    videos.sort(key=lambda v: v.get('publishedAt') or '', reverse=True)
    if len(videos) > MAX_VIDEOS:
        videos = videos[:MAX_VIDEOS]
        print(f'Trimmed to {MAX_VIDEOS} most recent videos')

    print(f'Total videos: {len(videos)}')

    with open(OUT_PATH, 'w', encoding='utf8', newline='') as f:
        json.dump({"videos": videos}, f, ensure_ascii=False, indent=2)
    print('Saved', OUT_PATH)


if __name__ == '__main__':
    fetch()
