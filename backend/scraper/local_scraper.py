"""
Local Playwright scraper with 10 parallel tabs, human behavior
Pushes results to Railway API
"""
import asyncio
import random
import re
import json
from datetime import datetime
from typing import Optional, Dict, List
import httpx

from playwright.async_api import async_playwright, Page, Browser

# Config
RAILWAY_API = "https://web-production-0bcb0.up.railway.app"
AMAZON_ASSOCIATE_TAG = "ss0ef2-21"
LOCAL_MODE = True  # Set to True when running locally

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


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
]


class HumanLikeScraper:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.results: List[Dict] = []
        self.stats = {"added": 0, "updated": 0, "errors": 0}
    
    async def init_browser(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
            ]
        )
    
    async def human_delay(self, min_ms: int = 1000, max_ms: int = 3000):
        await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)
    
    async def scroll_human_like(self, page: Page):
        """Scroll like a human would"""
        for _ in range(random.randint(3, 6)):
            await page.mouse.wheel(0, random.randint(200, 500))
            await self.human_delay(300, 800)
    
    async def move_mouse_human_like(self, page: Page):
        """Random mouse movements"""
        for _ in range(random.randint(2, 4)):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await page.mouse.move(x, y)
            await self.human_delay(100, 300)
    
    async def scrape_page(self, url: str, category: str) -> List[Dict]:
        """Scrape a single page with human behavior"""
        context = await self.browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport=random.choice(VIEWPORTS),
            ignore_https_errors=True,
        )
        
        page = await context.new_page()
        products = []
        
        try:
            # Navigate with human-like delay
            await self.human_delay(500, 1500)
            
            print(f"[Scraper] Loading: {url[:60]}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            
            # Wait for page to settle
            await self.human_delay(2000, 4000)
            
            # Human-like interactions
            await self.move_mouse_human_like(page)
            await self.scroll_human_like(page)
            await self.human_delay(1000, 2000)
            
            # Check for CAPTCHA
            content = await page.content()
            if "captcha" in content.lower():
                print("[Scraper] CAPTCHA detected!")
                await context.close()
                return products
            
            # Parse products
            products = await page.evaluate("""() => {
                const items = document.querySelectorAll('[data-component-type="s-search-result"]');
                return Array.from(items).slice(0, 30).map(item => {
                    const asin = item.getAttribute('data-asin');
                    const nameEl = item.querySelector('h2 a span, .a-size-medium');
                    const name = nameEl ? nameEl.textContent.trim() : '';
                    const priceEl = item.querySelector('.a-price .a-offscreen, .a-price-whole');
                    const priceText = priceEl ? priceEl.textContent.trim() : '';
                    const mrpEl = item.querySelector('.a-text-price .a-offscreen');
                    const mrpText = mrpEl ? mrpEl.textContent.trim() : '';
                    const discountEl = item.querySelector('.savingPercentage');
                    const discountText = discountEl ? discountEl.textContent.trim() : '';
                    const ratingEl = item.querySelector('.a-icon-star .a-icon-alt');
                    const ratingText = ratingEl ? ratingEl.textContent.trim() : '';
                    const reviewEl = item.querySelector('.a-size-base.s-underline-text');
                    const reviewText = reviewEl ? reviewEl.textContent.trim() : '';
                    const imgEl = item.querySelector('img.s-image');
                    const img = imgEl ? imgEl.src : '';
                    const urlEl = item.querySelector('h2 a');
                    const productUrl = urlEl ? urlEl.href : '';
                    
                    const priceMatch = priceText.match(/[\\d,]+/);
                    const price = priceMatch ? parseFloat(priceMatch[0].replace(',', '')) : 0;
                    const mrpMatch = mrpText.match(/[\\d,]+/);
                    const mrp = mrpMatch ? parseFloat(mrpMatch[0].replace(',', '')) : price;
                    const discountMatch = discountText.match(/(\\d+)/);
                    const discount = discountMatch ? parseInt(discountMatch[1]) : 0;
                    const ratingMatch = ratingText.match(/([\\d.]+)/);
                    const rating = ratingMatch ? parseFloat(ratingMatch[1]) : null;
                    const reviewMatch = reviewText.match(/([\\d,]+)/);
                    const reviews = reviewMatch ? parseInt(reviewMatch[1].replace(',', '')) : 0;
                    
                    return {
                        asin,
                        name,
                        price,
                        mrp,
                        discount,
                        rating,
                        reviews,
                        img,
                        productUrl,
                        isPrime: item.textContent.toLowerCase().includes('prime'),
                        isBestSeller: item.textContent.toLowerCase().includes('best seller'),
                        isAmazonChoice: item.textContent.toLowerCase().includes('amazon choice')
                    };
                }).filter(p => p.asin && p.name && p.price > 0);
            }""")
            
            # Add category and affiliate tag
            for p in products:
                p["category"] = category
                if p["productUrl"] and "tag=" not in p["productUrl"]:
                    separator = "&" if "?" in p["productUrl"] else "?"
                    p["productUrl"] = f"{p['productUrl']}{separator}tag={AMAZON_ASSOCIATE_TAG}"
            
            print(f"[Scraper] Found {len(products)} products")
            
        except Exception as e:
            print(f"[Scraper] Error: {e}")
        finally:
            await context.close()
        
        return products
    
    async def scrape_category_parallel(self, categories: List[str], concurrency: int = 5):
        """Scrape multiple categories in parallel with multiple tabs"""
        print(f"[Scraper] Starting parallel scrape of {len(categories)} categories ({concurrency} tabs)")
        
        await self.init_browser()
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrency)
        
        async def scrape_with_semaphore(cat):
            async with semaphore:
                products = await self.scrape_page(CATEGORY_URLS[cat], cat)
                # Push to Railway API
                for p in products:
                    await self.push_product(p)
                return len(products)
        
        tasks = [scrape_with_semaphore(cat) for cat in categories]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        print(f"[Scraper] Total products scraped: {sum(r for r in results if isinstance(r, int))}")
        await self.browser.close()
    
    async def push_product(self, product: Dict):
        """Push a single product to Railway API"""
        if not LOCAL_MODE:
            return
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{RAILWAY_API}/api/product/add",
                    json=product
                )
                if resp.status_code == 200:
                    self.stats["added"] += 1
                else:
                    self.stats["errors"] += 1
        except Exception as e:
            print(f"[Scraper] Push error: {e}")
            self.stats["errors"] += 1
    
    async def scrape_all(self):
        """Scrape all categories with human-like behavior"""
        await self.init_browser()
        
        for category, url in CATEGORY_URLS.items():
            print(f"\n{'='*60}")
            print(f"[Scraper] Scraping: {category}")
            print(f"{'='*60}")
            
            # Open 10 tabs for this category
            pages = []
            contexts = []
            
            for i in range(10):
                context = await self.browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport=random.choice(VIEWPORTS),
                    ignore_https_errors=True,
                )
                page = await context.new_page()
                pages.append(page)
                contexts.append(context)
            
            try:
                # Navigate all tabs with staggered delays
                tasks = []
                for i, page in enumerate(pages):
                    # Add page number to URL for pagination
                    page_url = f"{url}&page={i+1}"
                    tasks.append(self.scrape_page(page_url, category))
                    await self.human_delay(1000, 2000)  # Stagger tab opening
                
                all_products = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Collect all products
                for result in all_products:
                    if isinstance(result, list):
                        for p in result:
                            await self.push_product(p)
                
                print(f"[Scraper] Done with {category}")
                
            except Exception as e:
                print(f"[Scraper] Category error: {e}")
            finally:
                for ctx in contexts:
                    await ctx.close()
            
            # Wait between categories
            await self.human_delay(5000, 10000)
        
        await self.browser.close()
        print(f"\n[DONE] Scraped {self.stats['added']} products, {self.stats['errors']} errors")


async def main():
    scraper = HumanLikeScraper()
    await scraper.scrape_all()


if __name__ == "__main__":
    asyncio.run(main())
