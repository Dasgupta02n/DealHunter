"""
Simple HTTP-based scraper for Railway deployment
Uses httpx + BeautifulSoup (no Playwright needed)
"""
import asyncio
import random
import re
from datetime import datetime
from typing import Optional, Dict, List

import httpx
from bs4 import BeautifulSoup

from .user_agents import get_user_agent
from ..database.models import Product, PriceHistory, ScrapeLog, get_session

# Affiliate tag
AMAZON_ASSOCIATE_TAG = "ss0ef2-21"

CATEGORY_URLS = {
    "Shoes": "https://www.amazon.in/s?i=shoes&rh=n%3A2454168031&fs=true",
    "Beauty": "https://www.amazon.in/s?i=beauty&rh=n%3A1350386031&fs=true",
    "Health & Household": "https://www.amazon.in/s?i=hpc&rh=n%3A1534391031&fs=true",
    "Home": "https://www.amazon.in/s?i=home&rh=n%3A2454168031&fs=true",
    "Kitchen & Dining": "https://www.amazon.in/s?i=kitchen&rh=n%3A1534391031&fs=true",
    "Sports & Outdoors": "https://www.amazon.in/s?i=sports&rh=n%3A2454168031&fs=true",
    "Musical Instruments": "https://www.amazon.in/s?i=mi&rh=n%3A2454168031&fs=true",
    "Video Games": "https://www.amazon.in/s?i=videogames&rh=n%3A2454168031&fs=true",
    "Tools & Home Improvement": "https://www.amazon.in/s?i=hi&rh=n%3A2454168031&fs=true",
    "Content Creation": "https://www.amazon.in/s?i=electronics&rh=n%3A2454168031&fs=true",
    "Collectibles & Fine Art": "https://www.amazon.in/s?i=collectibles&rh=n%3A2454168031&fs=true",
}


class HTTPScraper:
    def __init__(self):
        self.session = get_session()
        self.stats = {"added": 0, "updated": 0, "errors": 0}
    
    async def fetch_page(self, url: str) -> Optional[str]:
        headers = {
            "User-Agent": get_user_agent(),
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for attempt in range(3):
                try:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        return resp.text
                    elif resp.status_code == 403:
                        print(f"[Scraper] Blocked (403) on attempt {attempt + 1}")
                        await asyncio.sleep(5)
                except Exception as e:
                    print(f"[Scraper] Error: {e}")
                    await asyncio.sleep(2)
            return None
    
    async def scrape_category(self, category: str) -> Dict:
        log = ScrapeLog(category=category, started_at=datetime.utcnow())
        url = CATEGORY_URLS.get(category)
        
        if not url:
            return {"found": 0, "added": 0, "updated": 0, "errors": 0}
        
        print(f"[Scraper] Scraping: {category}")
        products = []
        
        try:
            content = await self.fetch_page(url)
            if not content:
                print(f"[Scraper] Failed to fetch {category}")
                return {"found": 0, "added": 0, "updated": 0, "errors": 1}
            
            soup = BeautifulSoup(content, "html.parser")
            items = soup.select("[data-component-type='s-search-result']")
            
            for item in items[:30]:
                try:
                    product = self._parse_item(item, category)
                    if product:
                        products.append(product)
                except Exception as e:
                    print(f"[Scraper] Parse error: {e}")
                    continue
            
            print(f"[Scraper] Found {len(products)} in {category}")
            
            for pdata in products:
                self._save_product(pdata)
                await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"[Scraper] Error: {e}")
            log.errors = str(e)
        
        log.products_found = len(products)
        log.products_added = self.stats["added"]
        log.products_updated = self.stats["updated"]
        log.completed_at = datetime.utcnow()
        self.session.add(log)
        self.session.commit()
        
        return self.stats
    
    def _parse_item(self, item, category: str) -> Optional[Dict]:
        try:
            asin = item.get("data-asin")
            if not asin:
                return None
            
            name_elem = item.select_one("h2 a span, .a-size-medium")
            name = name_elem.text.strip() if name_elem else ""
            
            price_elem = item.select_one(".a-price .a-offscreen, .a-price-whole")
            price_text = price_elem.text.strip() if price_elem else ""
            price = self._extract_price(price_text)
            
            mrp_elem = item.select_one(".a-text-price .a-offscreen")
            mrp_text = mrp_elem.text.strip() if mrp_elem else ""
            mrp = self._extract_price(mrp_text)
            
            discount_elem = item.select_one(".savingPercentage")
            discount = 0
            if discount_elem:
                match = re.search(r'(\d+)', discount_elem.text)
                if match:
                    discount = int(match.group(1))
            
            rating_elem = item.select_one(".a-icon-star .a-icon-alt")
            rating = None
            if rating_elem:
                match = re.search(r'([\d.]+)', rating_elem.text)
                if match:
                    rating = float(match.group(1))
            
            review_elem = item.select_one(".a-size-base.s-underline-text")
            reviews = 0
            if review_elem:
                match = re.search(r'([\d,]+)', review_elem.text)
                if match:
                    reviews = int(match.group(1).replace(',', ''))
            
            img_elem = item.select_one("img.s-image")
            image = img_elem.get("src") if img_elem else ""
            
            url_elem = item.select_one("h2 a")
            product_url = f"https://www.amazon.in{url_elem.get('href')}" if url_elem else ""
            
            if product_url and "tag=" not in product_url:
                product_url = f"{product_url}&tag={AMAZON_ASSOCIATE_TAG}" if "?" in product_url else f"{product_url}?tag={AMAZON_ASSOCIATE_TAG}"
            
            is_prime = "prime" in item.text.lower()
            is_best = "best seller" in item.text.lower()
            is_choice = "amazon choice" in item.text.lower()
            
            if not name or not price:
                return None
            
            return {
                "asin": asin,
                "name": name,
                "category": category,
                "image_url": image,
                "product_url": product_url,
                "current_price": price,
                "current_mrp": mrp if mrp else price,
                "current_discount_percent": discount,
                "rating": rating,
                "review_count": reviews,
                "is_prime": is_prime,
                "is_best_seller": is_best,
                "is_amazon_choice": is_choice,
                "current_deal": discount >= 20,
            }
        except Exception as e:
            print(f"[Scraper] Parse error: {e}")
            return None
    
    def _extract_price(self, text: str) -> float:
        match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
        return float(match.group()) if match else 0.0
    
    def _save_product(self, data: Dict):
        try:
            existing = self.session.query(Product).filter_by(asin=data["asin"]).first()
            
            if existing:
                for key, val in data.items():
                    if hasattr(existing, key) and key not in ["asin", "first_seen"]:
                        setattr(existing, key, val)
                
                if data.get("current_price"):
                    if not existing.lowest_price_ever or data["current_price"] < existing.lowest_price_ever:
                        existing.lowest_price_ever = data["current_price"]
                        existing.lowest_price_date = datetime.utcnow()
                    if data.get("current_discount_percent", 0) > (existing.highest_discount_ever or 0):
                        existing.highest_discount_ever = data["current_discount_percent"]
                        existing.highest_discount_date = datetime.utcnow()
                
                existing.last_updated = datetime.utcnow()
                self.stats["updated"] += 1
            else:
                product = Product(**data)
                product.lowest_price_ever = data.get("current_price")
                product.lowest_price_date = datetime.utcnow()
                product.highest_discount_ever = data.get("current_discount_percent")
                product.highest_discount_date = datetime.utcnow()
                self.session.add(product)
                self.stats["added"] += 1
            
            history = PriceHistory(
                product_asin=data["asin"],
                mrp=data.get("current_mrp"),
                price=data.get("current_price"),
                discount_percent=data.get("current_discount_percent", 0),
                deal=data.get("current_deal", False),
            )
            self.session.add(history)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"[Scraper] DB error: {e}")
            self.stats["errors"] += 1


async def scrape_all():
    scraper = HTTPScraper()
    for cat in CATEGORY_URLS.keys():
        print(f"\n{'='*50}\nScraping: {cat}\n{'='*50}")
        await scraper.scrape_category(cat)
        await asyncio.sleep(3)
    print("\n[DONE] All categories scraped!")


if __name__ == "__main__":
    asyncio.run(scrape_all())
