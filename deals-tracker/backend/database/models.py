"""
SQLAlchemy models for the deals tracker
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    asin = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(500), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    subcategory = Column(String(200))
    image_url = Column(String(1000))
    product_url = Column(String(1000))
    affiliate_url = Column(String(2000))
    merchant = Column(String(200))
    rating = Column(Float)
    review_count = Column(Integer)
    is_prime = Column(Boolean, default=False)
    is_best_seller = Column(Boolean, default=False)
    is_amazon_choice = Column(Boolean, default=False)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Current price info
    current_mrp = Column(Float)
    current_price = Column(Float)
    current_discount_percent = Column(Integer)
    current_deal = Column(Boolean, default=False)
    
    # Historical stats (updated periodically)
    lowest_price_ever = Column(Float)
    lowest_price_date = Column(DateTime)
    highest_discount_ever = Column(Integer)
    highest_discount_date = Column(DateTime)
    avg_price_30d = Column(Float)
    
    def to_dict(self):
        return {
            'id': self.id,
            'asin': self.asin,
            'name': self.name,
            'category': self.category,
            'subcategory': self.subcategory,
            'image_url': self.image_url,
            'product_url': self.product_url,
            'affiliate_url': self.affiliate_url,
            'rating': self.rating,
            'review_count': self.review_count,
            'is_prime': self.is_prime,
            'is_best_seller': self.is_best_seller,
            'is_amazon_choice': self.is_amazon_choice,
            'current_mrp': self.current_mrp,
            'current_price': self.current_price,
            'current_discount_percent': self.current_discount_percent,
            'current_deal': self.current_deal,
            'lowest_price_ever': self.lowest_price_ever,
            'lowest_price_date': self.lowest_price_date.isoformat() if self.lowest_price_date else None,
            'highest_discount_ever': self.highest_discount_ever,
            'highest_discount_date': self.highest_discount_date.isoformat() if self.highest_discount_date else None,
            'avg_price_30d': self.avg_price_30d,
        }


class PriceHistory(Base):
    __tablename__ = 'price_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_asin = Column(String(20), nullable=False, index=True)
    mrp = Column(Float)
    price = Column(Float)
    discount_percent = Column(Integer)
    deal = Column(Boolean, default=False)
    scraped_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_product_scraped', 'product_asin', 'scraped_at'),
    )


class ScrapeLog(Base):
    __tablename__ = 'scrape_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(100))
    subcategory = Column(String(200))
    products_found = Column(Integer, default=0)
    products_added = Column(Integer, default=0)
    products_updated = Column(Integer, default=0)
    errors = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


# Database setup
def get_engine():
    return create_engine('sqlite:///deals.db', echo=False)

def get_session():
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)