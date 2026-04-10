"""
Background job scheduler for periodic scraping
"""
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers import interval, cron

from .scraper.amazon_scraper import scrape_all_categories, CATEGORY_URLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scrape_job(scrape_func, categories=None):
    """Setup the scrape job"""
    
    async def job():
        logger.info("[Scheduler] Starting scheduled scrape...")
        try:
            if categories:
                for cat in categories:
                    if cat in CATEGORY_URLS:
                        from .scraper.amazon_scraper import AmazonScraper
                        scraper = AmazonScraper()
                        stats = await scraper.scrape_category(cat)
                        logger.info(f"[Scheduler] {cat}: {stats}")
                        await asyncio.sleep(30)  # Wait between categories
            else:
                await scrape_func()
            logger.info("[Scheduler] Scrape completed!")
        except Exception as e:
            logger.error(f"[Scheduler] Scrape error: {e}")
    
    return job


def start_scheduler():
    """Start the background scheduler"""
    
    # Run full scrape every 6 hours
    scheduler.add_job(
        setup_scrape_job(scrape_all_categories),
        trigger=interval.HOURS(6),
        id="full_scrape",
        name="Full Category Scrape",
        replace_existing=True,
    )
    
    # Also run a quick scrape of deal-only products every hour
    scheduler.add_job(
        setup_scrape_job(None, categories=["Shoes", "Beauty", "Video Games"]),  # Top categories
        trigger=interval.HOURS(1),
        id="quick_scrape",
        name="Quick Deal Scrape",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("[Scheduler] Started - Full scrape every 6h, quick scrape hourly")


def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown()
    logger.info("[Scheduler] Stopped")
