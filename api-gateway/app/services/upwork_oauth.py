import sys
sys.path.insert(0, '/app')

import aiohttp
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import urlencode
import structlog
from app.config import settings

logger = structlog.get_logger()

class UpworkOAuthService:
    AUTH_URL = "https://www.upwork.com/ab/account-security/oauth2/authorize"
    TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
    
    def __init__(self):
        self.client_id = settings.UPWORK_CLIENT_ID
        self.client_secret = settings.UPWORK_CLIENT_SECRET
        self.redirect_uri = settings.UPWORK_REDIRECT_URI
        self._states: Dict[str, int] = {}
    
    def generate_auth_url(self, user_id: int) -> str:
        state = secrets.token_urlsafe(32)
        self._states[state] = user_id
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
        }
        
        return f"{self.AUTH_URL}?{urlencode(params)}"
    
    def validate_state(self, state: str) -> Optional[int]:
        return self._states.pop(state, None)
    
    async def exchange_code(self, code: str) -> Optional[Dict[str, Any]]:
        if not self.client_id or not self.client_secret:
            logger.error("upwork_credentials_missing")
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                    "code": code,
                }
                
                async with session.post(self.TOKEN_URL, data=data) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        error = await resp.text()
                        logger.error("upwork_token_error", status=resp.status, error=error)
                        return None
        except Exception as e:
            logger.error("upwork_exchange_exception", error=str(e))
            return None
    
    async def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        if not self.client_id or not self.client_secret:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                }
                
                async with session.post(self.TOKEN_URL, data=data) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        return None
        except Exception as e:
            logger.error("upwork_refresh_exception", error=str(e))
            return None
    
    @staticmethod
    def calculate_expires_at(expires_in: int) -> datetime:
        return datetime.utcnow() + timedelta(seconds=expires_in)

upwork_oauth = UpworkOAuthService()
