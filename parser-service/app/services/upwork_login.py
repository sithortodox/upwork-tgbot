import sys
sys.path.insert(0, '/app')

import json
import asyncio
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from datetime import datetime
import structlog

logger = structlog.get_logger()

class UpworkLoginService:
    UPWORK_LOGIN_URL = "https://www.upwork.com/ab/account-security/login"
    UPWORK_HOME_URL = "https://www.upwork.com/"
    UPWORK_FIND_WORK_URL = "https://www.upwork.com/nx/find-work/"
    
    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
    
    async def _get_browser(self, headless: bool = True) -> Browser:
        if self._browser is None:
            playwright = await async_playwright().start()
            
            launch_args = {
                "headless": headless,
                "args": ["--disable-blink-features=AutomationControlled"]
            }
            
            if self.proxy_url:
                launch_args["proxy"] = {"server": self.proxy_url}
            
            self._browser = await playwright.chromium.launch(**launch_args)
        
        return self._browser
    
    async def _create_context(self, cookies: Optional[str] = None) -> BrowserContext:
        browser = await self._get_browser()
        
        context_args = {
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        if self.proxy_url:
            context_args["proxy"] = {"server": self.proxy_url}
        
        self._context = await browser.new_context(**context_args)
        self._context.set_default_timeout(60000)
        self._context.set_default_navigation_timeout(60000)
        
        if cookies:
            try:
                cookies_list = json.loads(cookies)
                await self._context.add_cookies(cookies_list)
            except Exception as e:
                logger.error("failed_to_load_cookies", error=str(e))
        
        return self._context
    
    async def login(
        self,
        email: str,
        password: str,
        totp_secret: Optional[str] = None,
        existing_cookies: Optional[str] = None,
        headless: bool = True
    ) -> Dict[str, Any]:
        result = {
            "success": False,
            "cookies": None,
            "error": None,
            "requires_2fa": False
        }
        
        try:
            context = await self._create_context(existing_cookies)
            page = await context.new_page()
            
            await page.goto(self.UPWORK_HOME_URL, wait_until="networkidle")
            
            current_cookies = await context.cookies()
            if await self._is_logged_in(page, current_cookies):
                result["success"] = True
                result["cookies"] = json.dumps(current_cookies)
                logger.info("already_logged_in_via_cookies")
                return result
            
            await page.goto(self.UPWORK_LOGIN_URL, wait_until="networkidle")
            
            await page.fill('input[type="email"], input[name="login"]', email)
            await page.fill('input[type="password"], input[name="password"]', password)
            
            await page.click('button[type="submit"], input[type="submit"]')
            
            await asyncio.sleep(3)
            
            if await page.is_visible('input[name="otp"], input[id*="otp"], input[id*="2fa"]'):
                result["requires_2fa"] = True
                
                if totp_secret:
                    import pyotp
                    totp = pyotp.TOTP(totp_secret)
                    code = totp.now()
                    await page.fill('input[name="otp"], input[id*="otp"], input[id*="2fa"]', code)
                    await page.click('button[type="submit"], input[type="submit"]')
                    await asyncio.sleep(3)
            
            if await page.is_visible('input[id*="security"], input[name*="answer"]'):
                result["error"] = "Security question required - please login manually"
                return result
            
            await asyncio.sleep(2)
            
            current_url = page.url
            if "login" not in current_url.lower() and "ab/account-security" not in current_url.lower():
                current_cookies = await context.cookies()
                result["success"] = True
                result["cookies"] = json.dumps(current_cookies)
                logger.info("login_successful")
            else:
                error_text = await page.text_content('.alert-error, .error-message, [class*="error"]')
                result["error"] = error_text or "Login failed - check credentials"
        
        except Exception as e:
            result["error"] = str(e)
            logger.error("login_exception", error=str(e))
        
        finally:
            await self.close()
        
        return result
    
    async def _is_logged_in(self, page: Page, cookies: list) -> bool:
        upwork_cookies = [c for c in cookies if "upwork.com" in c.get("domain", "")]
        
        auth_tokens = [c for c in upwork_cookies if "auth" in c.get("name", "").lower() or "session" in c.get("name", "").lower()]
        
        if auth_tokens:
            try:
                await page.goto(self.UPWORK_FIND_WORK_URL, wait_until="networkidle", timeout=10000)
                
                if "login" not in page.url.lower():
                    return True
            except:
                pass
        
        return False
    
    async def get_projects_with_auth(
        self,
        cookies: str,
        search_query: Optional[str] = None,
        category: Optional[str] = None,
        max_results: int = 20
    ) -> list:
        projects = []
        
        try:
            context = await self._create_context(cookies)
            page = await context.new_page()
            
            url = self.UPWORK_FIND_WORK_URL
            if search_query:
                url += f"?q={search_query}"
            
            await page.goto(url, wait_until="networkidle")
            
            await asyncio.sleep(2)
            
            job_cards = await page.query_selector_all('[data-test="job-tile-list-item"], [class*="job-tile"]')
            
            for i, card in enumerate(job_cards[:max_results]):
                try:
                    title_el = await card.query_selector('h2 a, [data-test="job-title"]')
                    title = await title_el.inner_text() if title_el else ""
                    
                    link_el = await card.query_selector('h2 a')
                    href = await link_el.get_attribute('href') if link_el else ""
                    
                    desc_el = await card.query_selector('[data-test="job-description"], [class*="description"]')
                    description = await desc_el.inner_text() if desc_el else ""
                    
                    budget_el = await card.query_selector('[data-test="budget"], [class*="budget"]')
                    budget = await budget_el.inner_text() if budget_el else ""
                    
                    skills_els = await card.query_selector_all('[data-test="skill"] a, [class*="skill"] a')
                    skills = []
                    for skill_el in skills_els:
                        skill = await skill_el.inner_text()
                        skills.append(skill)
                    
                    project = {
                        "external_id": href.split("~")[-1].split("/")[0] if "~" in href else str(hash(title)),
                        "title": title.strip(),
                        "description": description.strip(),
                        "url": f"https://www.upwork.com{href}" if href.startswith("/") else href,
                        "budget": budget.strip(),
                        "skills": skills,
                    }
                    
                    projects.append(project)
                
                except Exception as e:
                    logger.error("failed_to_parse_job_card", error=str(e))
                    continue
        
        except Exception as e:
            logger.error("failed_to_get_projects", error=str(e))
        
        finally:
            await self.close()
        
        return projects
    
    async def close(self):
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None

upwork_login_service = UpworkLoginService()
