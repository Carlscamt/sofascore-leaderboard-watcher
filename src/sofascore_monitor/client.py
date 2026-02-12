try:
    from curl_cffi import requests as curl_requests
    HAS_CURL = True
except ImportError:
    import requests
    HAS_CURL = False

from .config import PROXY_URL, USER_AGENT

logger = logging.getLogger(__name__)

class UserNotFoundError(Exception):
    pass

class SofascoreClient:
    def __init__(self):
        self.base_url = "https://www.sofascore.com/api/v1"
        self.headers = {
            "Accept": "application/json",
            "Referer": "https://www.sofascore.com/",
            # UA is handled by impersonate, but we can set a fallback or specific one if needed
        }
        
        # Proxy Configuration
        self.proxy = None
        if PROXY_URL:
             self.proxy = PROXY_URL
             logger.info(f"Using Proxy: {PROXY_URL.split('@')[-1]}")

        if HAS_CURL:
            # Use chrome120 impersonation
            self.session = curl_requests.Session(impersonate="chrome120")
            if self.proxy:
                self.session.proxies = {"http": self.proxy, "https": self.proxy}
        else:
             self.session = requests.Session()
             self.session.headers.update(self.headers)
             self.session.headers["User-Agent"] = USER_AGENT
             if self.proxy:
                 self.session.proxies = {"http": self.proxy, "https": self.proxy}

    async def fetch(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Fetch data asynchronously using asyncio.to_thread for blocking IO.
        """
        return await asyncio.to_thread(self._fetch_sync, endpoint)

    def _fetch_sync(self, endpoint: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}{endpoint}"
        try:
            if HAS_CURL:
                # curl_cffi session
                response = self.session.get(
                    url, 
                    headers=self.headers, 
                    timeout=15
                )
            else:
                response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise UserNotFoundError(f"User not found at {endpoint}")
            elif response.status_code == 429:
                logger.warning("Rate limited (429).")
                return None 
            elif response.status_code == 403:
                logger.warning(f"403 Forbidden at {endpoint} (Anti-Bot Triggered)")
                return None
            else:
                logger.warning(f"Error fetching {endpoint}: {response.status_code}")
                return None
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Exception fetching {endpoint}: {e}")
            return None

    async def search(self, query: str) -> Optional[Dict[str, Any]]:
        endpoint = f"/search/all?q={query}"
        return await self.fetch(endpoint)

    async def get_user_predictions(self, user_id: str, page: int = 0) -> Optional[Dict[str, Any]]:
        if isinstance(user_id, str) and len(str(user_id)) > 15:
             endpoint = f"/user-account/{user_id}/predictions?page={page}"
        else:
             endpoint = f"/user/{user_id}/predictions?page={page}"
        return await self.fetch(endpoint)

    async def get_top_predictors(self):
        return await self.fetch("/user-account/vote-ranking")
