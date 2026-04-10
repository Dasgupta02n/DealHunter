"""
FastAPI backend for Deals Tracker
Run with: python -m backend.app
"""
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

from backend.database.models import Product, PriceHistory, ScrapeLog, get_session, init_db
from backend.scraper.amazon_scraper import AmazonScraper, CATEGORY_URLS, scrape_all_categories


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("[API] Database initialized")
    yield


app = FastAPI(
    title="Amazon Deals Tracker",
    description="Track and discover the best deals on Amazon.in",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    with open(frontend_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/deals")
async def get_deals(
    category: Optional[str] = None,
    min_discount: int = Query(default=0, ge=0, le=100),
    sort_by: str = "discount",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    session = get_session()
    query = session.query(Product).filter(
        Product.current_discount_percent >= min_discount,
        Product.current_price > 0,
    )
    
    if category:
        query = query.filter(Product.category == category)
    
    if sort_by == "discount":
        query = query.order_by(Product.current_discount_percent.desc())
    elif sort_by == "price_low":
        query = query.order_by(Product.current_price.asc())
    elif sort_by == "price_high":
        query = query.order_by(Product.current_price.desc())
    elif sort_by == "rating":
        query = query.order_by(Product.rating.desc().nullslast())
    elif sort_by == "updated":
        query = query.order_by(Product.last_updated.desc())
    
    total = query.count()
    products = query.offset(offset).limit(limit).all()
    
    return {"total": total, "offset": offset, "limit": limit, "products": [p.to_dict() for p in products]}


@app.get("/api/deals/best")
async def get_best_deals(limit: int = Query(default=20, ge=1, le=100)):
    session = get_session()
    products = session.query(Product).filter(
        Product.highest_discount_ever != None,
        Product.current_price > 0,
    ).order_by(Product.highest_discount_ever.desc()).limit(limit).all()
    return {"products": [p.to_dict() for p in products]}


@app.get("/api/deals/new-low")
async def get_new_low_prices(limit: int = Query(default=20, ge=1, le=100)):
    session = get_session()
    products = session.query(Product).filter(
        Product.current_price == Product.lowest_price_ever,
        Product.current_price > 0,
        Product.lowest_price_date != None,
    ).order_by(Product.lowest_price_date.desc()).limit(limit).all()
    return {"products": [p.to_dict() for p in products]}


@app.get("/api/categories")
async def get_categories():
    session = get_session()
    from sqlalchemy import func
    results = session.query(
        Product.category,
        func.count(Product.id).label("count"),
        func.max(Product.current_discount_percent).label("max_discount"),
    ).group_by(Product.category).all()
    categories = [{"name": r[0], "product_count": r[1], "max_discount": r[2]} for r in results]
    return {"categories": categories}


@app.get("/api/stats")
async def get_stats():
    session = get_session()
    from sqlalchemy import func
    total_products = session.query(func.count(Product.id)).scalar()
    total_deals = session.query(func.count(Product.id)).filter(Product.current_deal == True).scalar()
    avg_discount = session.query(func.avg(Product.current_discount_percent)).scalar()
    recent_scrapes = session.query(ScrapeLog).order_by(ScrapeLog.started_at.desc()).limit(5).all()
    return {
        "total_products": total_products or 0,
        "total_deals": total_deals or 0,
        "avg_discount": round(avg_discount or 0, 1),
        "last_scraped": recent_scrapes[0].completed_at.isoformat() if recent_scrapes else None,
        "recent_scrapes": [{"category": s.category, "products_found": s.products_found, "completed_at": s.completed_at.isoformat() if s.completed_at else None} for s in recent_scrapes],
    }


@app.get("/api/scrape")
async def trigger_scrape(category: Optional[str] = None):
    async def run_scrape():
        scraper = AmazonScraper()
        if category and category in CATEGORY_URLS:
            await scraper.scrape_category(category)
        else:
            await scrape_all_categories()
        await scraper.close()
    
    asyncio.create_task(run_scrape())
    return {"status": "started", "category": category or "all"}


@app.get("/api/product/{asin}")
async def get_product(asin: str):
    session = get_session()
    product = session.query(Product).filter(Product.asin == asin).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    history = session.query(PriceHistory).filter(
        PriceHistory.product_asin == asin,
        PriceHistory.scraped_at >= datetime.utcnow() - timedelta(days=30)
    ).order_by(PriceHistory.scraped_at).all()
    
    return {
        "product": product.to_dict(),
        "price_history": [{"price": h.price, "discount_percent": h.discount_percent, "scraped_at": h.scraped_at.isoformat()} for h in history],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
