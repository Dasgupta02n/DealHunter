"""
User-Agent rotation for stealth scraping
"""
import random
from fake_useragent import UserAgent

_ua = None

def get_user_agent():
    global _ua
    if _ua is None:
        try:
            _ua = UserAgent(fallbacks=['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'])
        except:
            pass
    
    try:
        return _ua.random
    except:
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def get_browser_args():
    """Args to make Playwright stealthier"""
    return [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu',
        '--disable-web-security',
        '--disable-features=IsolateOrigins,site-per-process',
        '--window-size=1920,1080',
    ]

# Common viewport sizes
VIEWPORTS = [
    {'width': 1920, 'height': 1080},
    {'width': 1366, 'height': 768},
    {'width': 1536, 'height': 864},
    {'width': 1440, 'height': 900},
]

def get_viewport():
    return random.choice(VIEWPORTS)