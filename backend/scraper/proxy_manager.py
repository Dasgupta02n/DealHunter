"""
Free proxy rotation to avoid IP bans
"""
import asyncio
import httpx
import random
from typing import Optional, List

# Free proxy sources (updated periodically)
PROXY_LIST_URLS = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
]

class ProxyManager:
    def __init__(self):
        self.proxies: List[str] = []
        self._loaded = False
    
    async def load_proxies(self):
        """Fetch fresh proxies from multiple sources"""
        if self._loaded and self.proxies:
            return
        
        all_proxies = set()
        
        async with httpx.AsyncClient(timeout=15) as client:
            for url in PROXY_LIST_URLS:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        lines = resp.text.strip().split('\n')
                        for line in lines:
                            line = line.strip()
                            if line and ':' in line:
                                # Skip without port (we need port)
                                all_proxies.add(line)
                except Exception:
                    pass
        
        # Filter to only Indian proxies or common high uptime proxies
        self.proxies = list(all_proxies)
        random.shuffle(self.proxies)
        self._loaded = True
        print(f"[ProxyManager] Loaded {len(self.proxies)} proxies")
    
    async def get_random_proxy(self) -> Optional[str]:
        """Get a random proxy from the list"""
        if not self._loaded:
            await self.load_proxies()
        
        if not self.proxies:
            return None
        
        return random.choice(self.proxies)
    
    async def test_proxy(self, proxy: str) -> bool:
        """Test if a proxy is working"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "http://httpbin.org/ip",
                    proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
                    timeout=5
                )
                return resp.status_code == 200
        except:
            return False
    
    async def get_working_proxy(self) -> Optional[str]:
        """Get a proxy that actually works"""
        proxies_to_test = random.sample(self.proxies, min(10, len(self.proxies)))
        
        for proxy in proxies_to_test:
            if await self.test_proxy(proxy):
                return proxy
        
        # Refresh if none work
        self._loaded = False
        await self.load_proxies()
        return await self.get_random_proxy()

# Global instance
proxy_manager = ProxyManager()