"""
Amazon.in stealth scraper using Playwright
Mimics human behavior to avoid detection
"""
import asyncio
import random
import re
from datetime import datetime
from typing import Optional, Dict, List

from playwright.async_api import async_playwright, Page, Browser, ProxySettings
from bs4 import BeautifulSoup

from .user_agents import get_user_agent, get_browser_args, get_viewport
from .proxy_manager import proxy_manager
from ..database.models import Product, PriceHistory, ScrapeLog, get_session


# Affiliate tag for Amazon Associates
AMAZON_ASSOCIATE_TAG = "ss0ef2-21"

CATEGORY_URLS = {
    "Shoes": "https://www.amazon.in/s?i=shoes&rh=n%3A2454168031&fs=true",
    "Beauty": "https://www.amazon.in/s?i=beauty&rh=n%3A1350386031&fs=true",
    "Health & Household": "https://www.amazon.in/s?i=hpc&rh=n%3A1534391031&fs=true",
    "Home": "https://www.amazon.in/s?i=home&rh=n%3A2454168031&fs=true",
    "Kitchen & Dining": "https://www.amazon.in/s?i=kitchen&rh=n%3A2454168031&fs=true",
    "Sports & Outdoors": "https://www.amazon.in/s?i=sports&rh=n%3A2454168031&fs=true",
    "Musical Instruments": "https://www.amazon.in/s?i=mi&rh=n%3A2454168031&fs=true",
    "Video Games": "https://www.amazon.in/s?i=videogames&rh=n%3A2454168031&fs=true",
    "Tools & Home Improvement": "https://www.amazon.in/s?i=hi&rh=n%3A2454168031&fs=true",
    "Content Creation": "https://www.amazon.in/s?i=electronics&rh=n%3A2454168031&fs=true",
    "Collectibles & Fine Art": "https://www.amazon.in/s?i=collectibles&rh=n%3A2454168031&fs=true",
}


class AmazonScraper:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.session = get_session()
        self.stats = {"added": 0, "updated": 0, "errors": 0}
    
    async def init_browser(self, use_proxy: bool = True):
        """Initialize stealth browser"""
        playwright = await async_playwright().start()
        
        # Try proxy first
        proxy = None
        if use_proxy:
            proxy = await proxy_manager.get_working_proxy()
        
        browser_args = get_browser_args()
        viewport = get_viewport()
        user_agent = get_user_agent()
        
        launch_options = {
            "headless": True,
            "args": browser_args,
        }
        
        if proxy:
            proxy_obj = ProxySettings(
                server=f"http://{proxy.split(':')[0]}:{proxy.split(':')[1]}"
            )
            launch_options["proxy"] = proxy_obj
        
        self.browser = await playwright.chromium.launch(**launch_options)
        self.context = await self.browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
            ignore_https_errors=True,
        )
        self.page = await self.context.new_page()
        
        # Block heavy resources that aren't needed
        await self.context.route("**/*.css", lambda route: route.abort())
        
        # Add realistic headers
        await self.context.set_extra_http_headers({
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })
    
    async def human_delay(self, min_ms: int = 1000, max_ms: int = 3000):
        """Random delay to mimic human behavior"""
        await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)
    
    async def scroll_page(self, scrolls: int = 3):
        """Scroll page like a human would"""
        for _ in range(scrolls):
            await self.page.mouse.wheel(0, random.randint(300, 600))
            await self.human_delay(500, 1500)
    
    async def handle_captcha(self) -> bool:
        """Detect and handle captcha"""
        content = await self.page.content()
        if "captcha" in content.lower() or "verify" in content.lower():
            print("[Scraper] CAPTCHA detected, rotating...")
            await self.context.clear_cookies()
            return True
        return False
    
    async def scrape_search_page(self, url: str, category: str) -> List[Dict]:
        """Scrape a category search page for products"""
        products = []
        
        try:
            print(f"[Scraper] Fetching: {url}")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self.human_delay(2000, 4000)
            
            # Scroll to load products
            await self.scroll_page(scrolls=4)
            
            # Check for captcha
            if await self.handle_captcha():
                return products
            
            # Get page content
            content = await self.page.content()
            soup = BeautifulSoup(content, "lxml")
            
            # Find product elements (Amazon search results)
            product_elements = soup.select("[data-component-type='s-search-result']")
            
            for elem in product_elements:
                try:
                    product = self._parse_product_element(elem, category)
                    if product:
                        products.append(product)
                except Exception as e:
                    print(f"[Scraper] Error parsing product: {e}")
                    continue
            
            print(f"[Scraper] Found {len(products)} products in {category}")
            
        except Exception as e:
            print(f"[Scraper] Error scraping {url}: {e}")
        
        return products
    
    def _parse_product_element(self, elem, category: str) -> Optional[Dict]:
        """Parse a single product element"""
        try:
            # ASIN
            asin = elem.get("data-asin")
            if not asin:
                return None
            
            # Name
            name_elem = elem.select_one("h2 a span, .a-size-medium")
            name = name_elem.text.strip() if name_elem else ""
            
            # Price
            price_elem = elem.select_one(".a-price .a-offscreen, .a-price-whole")
            price_text = price_elem.text.strip() if price_elem else ""
            price = self._extract_price(price_text)
            
            # MRP (original price)
            mrp_elem = elem.select_one(".a-text-price .a-offscreen, .a-text-price span")
            mrp_text = mrp_elem.text.strip() if mrp_elem else ""
            mrp = self._extract_price(mrp_text)
            
            # Discount percent
            discount_elem = elem.select_one(".savingPercentage, .a-color-price")
            discount_percent = 0
            if discount_elem:
                discount_text = discount_elem.text.strip()
                match = re.search(r'(\d+)', discount_text)
                if match:
                    discount_percent = int(match.group(1))
            
            # Rating
            rating_elem = elem.select_one(".a-icon-star .a-icon-alt, [aria-label*='out of']")
            rating = None
            if rating_elem:
                match = re.search(r'([\d.]+)', rating_elem.text)
                if match:
                    rating = float(match.group(1))
            
            # Review count
            review_elem = elem.select_one(".a-size-base.s-underline-text")
            review_count = 0
            if review_elem:
                match = re.search(r'([\d,]+)', review_elem.text)
                if match:
                    review_count = int(match.group(1).replace(',', ''))
            
            # Image
            img_elem = elem.select_one("img.s-image")
            image_url = img_elem.get("src") if img_elem else ""
            
            # Badges
            is_prime = ".prime" in elem.text.lower()
            is_best_seller = "best seller" in elem.text.lower()
            is_amazon_choice = "amazon choice" in elem.text.lower()
            
            # URL with affiliate tag
            url_elem = elem.select_one("h2 a")
            product_url = f"https://www.amazon.in{url_elem.get('href')}" if url_elem else ""
            if product_url and "tag=" not in product_url:
                product_url = f"{product_url}&tag={AMAZON_ASSOCIATE_TAG}" if "?" in product_url else f"{product_url}?tag={AMAZON_ASSOCIATE_TAG}"
            
            if not name or not price:
                return None
            
            return {
                "asin": asin,
                "name": name,
                "category": category,
                "image_url": image_url,
                "product_url": product_url,
                "current_price": price,
                "current_mrp": mrp if mrp else price,
                "current_discount_percent": discount_percent,
                "rating": rating,
                "review_count": review_count,
                "is_prime": is_prime,
                "is_best_seller": is_best_seller,
                "is_amazon_choice": is_amazon_choice,
                "current_deal": discount_percent >= 20,
            }
        except Exception as e:
            print(f"[Scraper] Parse error: {e}")
            return None
    
    def _extract_price(self, text: str) -> float:
        """Extract price from text"""
        if not text:
            return 0.0
        match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
        if match:
            return float(match.group())
        return 0.0
    
    async def save_product(self, product_data: Dict) -> bool:
        """Save or update product in database"""
        try:
            asin = product_data["asin"]
            existing = self.session.query(Product).filter_by(asin=asin).first()
            
            if existing:
                # Update existing
                for key, value in product_data.items():
                    if hasattr(existing, key) and key not in ["asin", "first_seen"]:
                        setattr(existing, key, value)
                
                # Update historical stats
                if product_data.get("current_price", 0) > 0:
                    if not existing.lowest_price_ever or product_data["current_price"] < existing.lowest_price_ever:
                        existing.lowest_price_ever = product_data["current_price"]
                        existing.lowest_price_date = datetime.utcnow()
                    
                    if product_data.get("current_discount_percent", 0) > (existing.highest_discount_ever or 0):
                        existing.highest_discount_ever = product_data["current_discount_percent"]
                        existing.highest_discount_date = datetime.utcnow()
                
                existing.last_updated = datetime.utcnow()
                self.stats["updated"] += 1
            else:
                # Create new
                product = Product(**product_data)
                product.lowest_price_ever = product_data.get("current_price")
                product.lowest_price_date = datetime.utcnow()
                product.highest_discount_ever = product_data.get("current_discount_percent")
                product.highest_discount_date = datetime.utcnow()
                self.session.add(product)
                self.stats["added"] += 1
            
            # Add price history
            history = PriceHistory(
                product_asin=asin,
                mrp=product_data.get("current_mrp"),
                price=product_data.get("current_price"),
                discount_percent=product_data.get("current_discount_percent", 0),
                deal=product_data.get("current_deal", False),
            )
            self.session.add(history)
            
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            print(f"[Scraper] DB error: {e}")
            self.stats["errors"] += 1
            return False
    
    async def scrape_category(self, category: str) -> Dict:
        """Scrape a single category"""
        log = ScrapeLog(category=category, started_at=datetime.utcnow())
        
        url = CATEGORY_URLS.get(category)
        if not url:
            print(f"[Scraper] No URL for category: {category}")
            return {"found": 0, "added": 0, "updated": 0, "errors": 0}
        
        await self.init_browser()
        
        try:
            products = await self.scrape_search_page(url, category)
            log.products_found = len(products)
            
            for product_data in products:
                await self.save_product(product_data)
                await self.human_delay(1000, 2000)  # Be nice to Amazon
            
        except Exception as e:
            log.errors = str(e)
            print(f"[Scraper] Category error: {e}")
        finally:
            log.completed_at = datetime.utcnow()
            log.products_added = self.stats["added"]
            log.products_updated = self.stats["updated"]
            self.session.add(log)
            self.session.commit()
            await self.browser.close()
        
        return self.stats
    
    async def close(self):
        """Cleanup"""
        if self.browser:
            await self.browser.close()


async def scrape_all_categories():
    """Main function to scrape all categories"""
    scraper = AmazonScraper()
    
    for category in CATEGORY_URLS.keys():
        print(f"\n{'='*50}")
        print(f"[Main] Scraping: {category}")
        print(f"{'='*50}")
        
        stats = await scraper.scrape_category(category)
        print(f"[Main] Results: {stats}")
        
        # Wait between categories
        await asyncio.sleep(random.uniform(30, 60))
    
    await scraper.close()
    print("\n[Main] All categories scraped!")


if __name__ == "__main__":
    asyncio.run(scrape_all_categories())
