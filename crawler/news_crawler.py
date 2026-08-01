import feedparser
import requests
import json
import os
import time
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import sys

# Set UTF-8 encoding for stdout
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.join(os.path.dirname(__file__), '..')
NEWS_PATH = os.path.join(ROOT, 'public', 'news.json')
FEEDS_PATH = os.path.join(ROOT, 'public', 'news_feeds.json')

class NewsCrawler:
    def __init__(self):
        self.news_sources = self.load_news_sources()
        self.existing_news = self.load_existing_news()
    
    def load_news_sources(self):
        """Load news sources from config file"""
        try:
            with open(FEEDS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [source for source in data.get('news_sources', []) if source.get('enabled', True)]
        except Exception as e:
            print(f"Error loading news sources: {e}")
            return []
        
    def load_existing_news(self):
        """Load existing news to avoid duplicates"""
        if os.path.exists(NEWS_PATH):
            try:
                with open(NEWS_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('news', [])
            except Exception as e:
                print(f"Error loading existing news: {e}")
        return []
    
    def save_news(self, news_list):
        """Save news to JSON file"""
        news_data = {
            'last_updated': datetime.now().isoformat(),
            'total_news': len(news_list),
            'news': news_list
        }
        
        with open(NEWS_PATH, 'w', encoding='utf-8') as f:
            json.dump(news_data, f, ensure_ascii=False, indent=2)
        
        print(f"Saved {len(news_list)} news articles to {NEWS_PATH}")
    
    def fetch_rss_news(self, source):
        """Fetch news from RSS feed"""
        try:
            print(f"Fetching RSS from {source['name']}: {source['url']}")
            feed = feedparser.parse(source['url'])
            
            news_items = []
            for entry in feed.entries[:20]:  # Limit to 20 latest
                # Extract content
                title = entry.get('title', '')
                link = entry.get('link', '')
                summary = entry.get('summary', '')
                published = entry.get('published_parsed')
                
                # Convert published date
                published_iso = None
                if published:
                    published_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', published)
                
                # Check if news is recent (within last 7 days)
                if published_iso:
                    try:
                        pub_date = datetime.fromisoformat(published_iso.replace('Z', '+00:00'))
                        now = datetime.now(pub_date.tzinfo) if pub_date.tzinfo else datetime.now()
                        if pub_date < now - timedelta(days=7):
                            continue
                    except Exception as e:
                        print(f"Date parsing error: {e}")
                        continue
                
                # Filter Liên Quân related content
                if self.is_lienquan_related(title, summary):
                    # Extract image from RSS entry
                    image_url = self.extract_image_url(entry)
                    
                    news_item = {
                        'id': self.generate_news_id(link),
                        'title': title,
                        'link': link,
                        'summary': summary[:500],  # Limit summary length
                        'image_url': image_url,
                        'source': source['name'],
                        'source_url': source['url'],
                        'published_at': published_iso,
                        'crawled_at': datetime.now().isoformat(),
                        'category': self.categorize_news(title, summary),
                        'priority': source.get('priority', 5)
                    }
                    news_items.append(news_item)
            
            return news_items
            
        except Exception as e:
            print(f"Error fetching RSS from {source['name']}: {e}")
            return []
    
    def scrape_news(self, source):
        """Scrape news from website (placeholder for future implementation)"""
        # This would require BeautifulSoup and more complex scraping
        # For now, we'll focus on RSS feeds
        print(f"Scraping not implemented yet for {source['name']}")
        return []
    
    def is_lienquan_related(self, title, content):
        """Check if content is related to Liên Quân Mobile"""
        text = (title + ' ' + content).lower()
        
        # Keywords that indicate Liên Quân content
        lienquan_keywords = [
            'liên quân', 'lien quan', 'aov', 'arena of valor',
            'garena', 'mobile legends', 'mlbb', 'mobile gaming',
            'esports', 'tướng', 'tướng mới', 'skin', 'bản cập nhật',
            'tournament', 'giải đấu', 'pro player', 'cao thủ',
            'meta', 'build', 'bảng ngọc', 'rank', 'leo rank'
        ]
        
        # Exclude keywords
        exclude_keywords = [
            'pubg', 'free fire', 'call of duty', 'valorant',
            'lol', 'league of legends', 'dota', 'csgo'
        ]
        
        # Check for Liên Quân keywords
        has_lienquan = any(keyword in text for keyword in lienquan_keywords)
        
        # Check for exclude keywords
        has_exclude = any(keyword in text for keyword in exclude_keywords)
        
        return has_lienquan and not has_exclude
    
    def categorize_news(self, title, content):
        """Categorize news based on content"""
        text = (title + ' ' + content).lower()
        
        if any(word in text for word in ['tướng mới', 'hero mới', 'tướng', 'hero']):
            return 'tướng'
        elif any(word in text for word in ['skin', 'trang phục', 'cosmetic']):
            return 'skin'
        elif any(word in text for word in ['bản cập nhật', 'update', 'patch']):
            return 'cập nhật'
        elif any(word in text for word in ['tournament', 'giải đấu', 'esports']):
            return 'esports'
        elif any(word in text for word in ['meta', 'build', 'bảng ngọc']):
            return 'meta'
        else:
            return 'tin tức'
    
    def extract_image_url(self, entry):
        """Extract image URL from RSS entry"""
        # Try different ways to get image
        image_url = None
        
        # Method 1: Try to fetch og:image from the article URL
        link = entry.get('link', '')
        if link and not link.includes('example.com') if hasattr(link, 'includes') else (link and 'example.com' not in link):
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                # Use a fast timeout (3 seconds) to avoid blocking the crawler
                res = requests.get(link, headers=headers, timeout=3)
                if res.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(res.text, 'html.parser')
                    meta_og_image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
                    if meta_og_image and meta_og_image.get('content'):
                        image_url = meta_og_image.get('content')
                        print(f"-> Successfully extracted og:image from HTML: {image_url}")
            except Exception as e:
                print(f"Error fetching og:image from HTML {link}: {e}")

        # Method 2: Check media:content
        if not image_url and hasattr(entry, 'media_content'):
            for media in entry.media_content:
                if media.get('type', '').startswith('image/'):
                    image_url = media.get('url')
                    break
        
        # Method 3: Check media:thumbnail
        if not image_url and hasattr(entry, 'media_thumbnail'):
            image_url = entry.media_thumbnail[0].get('url')
        
        # Method 4: Check enclosures
        if not image_url and hasattr(entry, 'enclosures'):
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'):
                    image_url = enclosure.get('href')
                    break
        
        # Method 5: Extract from summary HTML
        if not image_url:
            summary = entry.get('summary', '')
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
            if img_match:
                image_url = img_match.group(1)
        
        return image_url
    
    def generate_news_id(self, url):
        """Generate unique ID for news item"""
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:12]
    
    def crawl_all_sources(self):
        """Crawl news from all sources"""
        all_news = []
        
        for source in self.news_sources:
            try:
                if source['type'] == 'rss':
                    news_items = self.fetch_rss_news(source)
                elif source['type'] == 'scrape':
                    news_items = self.scrape_news(source)
                
                all_news.extend(news_items)
                print(f"Found {len(news_items)} news from {source['name']}")
                
                # Small delay between requests
                time.sleep(1)
                
            except Exception as e:
                print(f"Error processing {source['name']}: {e}")
                continue
        
        # Remove duplicates and merge with existing news
        existing_ids = {news['id'] for news in self.existing_news}
        new_news = [news for news in all_news if news['id'] not in existing_ids]
        
        # Combine existing and new news
        combined_news = new_news + self.existing_news
        
        # Sort by published date (newest first)
        combined_news.sort(key=lambda x: x.get('published_at') or '1970-01-01T00:00:00Z', reverse=True)
        
        # Keep only last 100 news items
        combined_news = combined_news[:100]
        
        print(f"Total new news found: {len(new_news)}")
        print(f"Total news in database: {len(combined_news)}")
        
        return combined_news
    
    def run(self):
        """Main crawl function"""
        print("Starting news crawl...")
        print(f"Existing news count: {len(self.existing_news)}")
        
        news_list = self.crawl_all_sources()
        self.save_news(news_list)
        
        print("News crawl completed!")

if __name__ == '__main__':
    crawler = NewsCrawler()
    crawler.run()
