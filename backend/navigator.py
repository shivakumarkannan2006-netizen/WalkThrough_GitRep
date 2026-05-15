"""
ShieldNavigator - Playwright-based browser automation with BFS traversal
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Callable
from urllib.parse import urljoin, urlparse
from collections import deque
import json
import uuid
from datetime import datetime

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from config import get_settings

logger = logging.getLogger(__name__)

class ShieldNavigator:
    """
    Autonomous browser navigator using Playwright with BFS traversal
    Handles both authenticated and unauthenticated paths
    """

    def __init__(
        self,
        target_url: str,
        audit_session_id: str,
        supabase_client,
        credentials: Optional[Tuple[str, str]] = None,
        broadcast_fn: Optional[Callable] = None,
        stop_flag_fn: Optional[Callable[[], bool]] = None,
    ):
        self.target_url = target_url
        self.audit_session_id = audit_session_id
        self.supabase = supabase_client
        self.credentials = credentials
        self.broadcast = broadcast_fn or (lambda x: None)
        # Callable that returns True when the user has requested a stop
        self._stop_flag = stop_flag_fn or (lambda: False)

        self.settings = get_settings()
        self.playwright = None
        self.browser = None

        # Navigation state
        self.visited_urls = set()
        self.discovered_urls = set()
        self.pages_data = []
        self.base_domain = urlparse(target_url).netloc

        # Performance tracking
        self.baseline_load_time = None
        self.performance_data = {}

    async def start_traversal(self) -> List[Dict]:
        """Start BFS traversal of website"""
        try:
            logger.info(f"Starting traversal of {self.target_url}")
            await self.broadcast({"type": "traversal_started", "target_url": self.target_url})

            async with async_playwright() as playwright:
                self.playwright = playwright
                self.browser = await playwright.chromium.launch(
                    headless=self.settings.PLAYWRIGHT_HEADLESS,
                    args=self.settings.PLAYWRIGHT_ARGS,
                )

                # Create two independent contexts: authenticated and unauthenticated
                unauth_context = await self.browser.new_context()
                auth_context = await self.browser.new_context() if self.credentials else None

                try:
                    # Start unauthenticated traversal
                    logger.info("Starting unauthenticated path traversal")
                    await self._traverse_bfs(unauth_context, authenticated=False)

                    # Start authenticated traversal if credentials provided
                    if auth_context and self.credentials:
                        logger.info("Starting authenticated path traversal")
                        await self._traverse_bfs(auth_context, authenticated=True)

                finally:
                    # Always close contexts and browser — prevents zombie processes on crash
                    try:
                        await unauth_context.close()
                    except Exception:
                        pass
                    if auth_context:
                        try:
                            await auth_context.close()
                        except Exception:
                            pass
                    try:
                        await self.browser.close()
                        self.browser = None
                    except Exception as e:
                        logger.error(f"Error closing browser: {e}")

            logger.info(f"Traversal completed. Discovered {len(self.pages_data)} pages")
            await self.broadcast({"type": "traversal_completed", "total_pages": len(self.pages_data)})

            return self.pages_data

        except Exception as e:
            logger.error(f"Traversal error: {e}")
            await self.broadcast({"type": "traversal_error", "error": str(e)})
            raise

    async def _traverse_bfs(self, context: BrowserContext, authenticated: bool = False):
        """BFS traversal of discovered URLs"""
        queue = deque([self.target_url])
        visited_in_context = set()

        while queue and len(visited_in_context) < self.settings.MAX_PAGES_PER_AUDIT:
            if self._stop_flag():
                logger.info(f"BFS stopped by user flag at {len(visited_in_context)} pages")
                break

            current_url = queue.popleft()

            if current_url in visited_in_context:
                continue

            visited_in_context.add(current_url)
            logger.info(f"{'[AUTH]' if authenticated else '[UNAUTH]'} Visiting: {current_url}")

            try:
                page = await context.new_page()
                page_data = await self._analyze_page(page, current_url, authenticated)

                if page_data:
                    self.pages_data.append(page_data)

                    # Extract all clickable elements and links
                    new_urls = await self._extract_clickable_elements(page, current_url)

                    # Add new URLs to queue (avoid duplicates and external links)
                    for url in new_urls:
                        normalized_url = self._normalize_url(url)
                        if (
                            normalized_url not in self.visited_urls
                            and normalized_url not in visited_in_context
                            and self._is_same_domain(normalized_url)
                            and len(visited_in_context) < self.settings.MAX_PAGES_PER_AUDIT
                        ):
                            queue.append(normalized_url)
                            self.discovered_urls.add(normalized_url)

                await page.close()

            except Exception as e:
                logger.error(f"Error analyzing {current_url}: {e}")
                self._log_navigator_error(current_url, str(e))

            # Broadcast progress
            await self.broadcast({
                "type": "page_discovered",
                "url": current_url,
                "authenticated": authenticated,
                "pages_discovered": len(self.pages_data),
            })

    async def _analyze_page(self, page: Page, url: str, authenticated: bool) -> Optional[Dict]:
        """Analyze a single page and return page data"""
        try:
            start_time = time.time()

            # Handle login if authenticated and not yet logged in
            if authenticated and self.credentials and not await self._is_logged_in(page):
                await self._pseudo_login(page)

            # Navigate to URL with auto-wait
            await page.goto(url, wait_until="networkidle", timeout=self.settings.PAGE_LOAD_TIMEOUT_MS)

            load_time_ms = int((time.time() - start_time) * 1000)

            # Record baseline on first page
            if self.baseline_load_time is None:
                self.baseline_load_time = load_time_ms
                logger.info(f"Baseline load time set: {self.baseline_load_time}ms")

            # Get page accessibility snapshot
            axe_tree = await page.accessibility.snapshot()

            # Extract page metadata
            page_title = await page.title()
            meta_description = await page.evaluate(
                "document.querySelector('meta[name=description]')?.getAttribute('content')"
            )

            # Store page snapshot in Supabase
            audit_page_id = str(uuid.uuid4())  # default if DB insert fails
            try:
                audit_page_response = self.supabase.table("audit_pages").insert({
                    "audit_session_id": self.audit_session_id,
                    "url": url,
                    "http_status_code": 200,
                    "load_time_ms": load_time_ms,
                    "is_accessible_without_auth": not authenticated,
                    "page_title": page_title,
                    "meta_description": meta_description,
                }).execute()

                if audit_page_response.data:
                    audit_page_id = audit_page_response.data[0]["id"]

                    self.supabase.table("audit_page_snapshots").insert({
                        "audit_page_id": audit_page_id,
                        "axe_tree_json": axe_tree or {},
                        "page_title": page_title,
                        "meta_description": meta_description,
                    }).execute()
            except Exception as e:
                logger.error(f"Error storing page data: {e}")

            # Check for performance bottleneck
            if self.baseline_load_time is not None and \
                    load_time_ms > self.baseline_load_time + self.settings.PERFORMANCE_BASELINE_THRESHOLD_MS:
                logger.warning(f"Performance bottleneck detected: {load_time_ms}ms vs baseline {self.baseline_load_time}ms")
                try:
                    self.supabase.table("performance_bottlenecks").insert({
                        "audit_session_id": self.audit_session_id,
                        "page_url": url,
                        "load_time_ms": load_time_ms,
                        "baseline_load_time_ms": self.baseline_load_time,
                        "difference_ms": load_time_ms - self.baseline_load_time,
                    }).execute()
                except Exception as e:
                    logger.error(f"Error recording performance bottleneck: {e}")

            # Extract AXTree snapshot and page content before page.close() is called
            # by _traverse_bfs. Crew agents use this snapshot, not the live page object.
            page_html = ""
            try:
                page_html = await page.content()
            except Exception:
                pass

            return {
                "audit_page_id": audit_page_id,
                "url": url,
                "page_title": page_title,
                "load_time_ms": load_time_ms,
                "axe_tree": axe_tree,
                "authenticated": authenticated,
                "page_html": page_html,
                # page_object intentionally omitted — page will be closed by caller
            }

        except Exception as e:
            logger.error(f"Error analyzing page {url}: {e}")
            return None

    async def _extract_clickable_elements(self, page: Page, current_url: str) -> List[str]:
        """Extract all clickable elements and links from page"""
        urls = []

        try:
            # Get all links
            links = await page.query_selector_all("a[href]")
            for link in links:
                href = await link.get_attribute("href")
                if href:
                    absolute_url = urljoin(current_url, href)
                    urls.append(absolute_url)

            # Get all buttons that might be links (simulate clicks)
            buttons = await page.query_selector_all("button, [role='button']")
            # Note: Actual click simulation happens in crew agents

            # Get form submission URLs
            forms = await page.query_selector_all("form")
            for form in forms:
                action = await form.get_attribute("action")
                if action:
                    absolute_url = urljoin(current_url, action)
                    urls.append(absolute_url)

        except Exception as e:
            logger.error(f"Error extracting elements from {current_url}: {e}")

        return urls

    async def _pseudo_login(self, page: Page):
        """Attempt to log in using provided credentials"""
        if not self.credentials or not self.credentials[0]:
            return

        username, password = self.credentials

        try:
            logger.info("Attempting pseudo-login")

            # Find username/email field
            username_field = None
            selectors_to_try = [
                "input[type='email']",
                "input[name*='email'], input[name*='username'], input[name*='user'], input[id*='email'], input[id*='username']",
                "input[type='text']",
            ]

            for selector in selectors_to_try:
                try:
                    username_field = await page.query_selector(selector)
                    if username_field:
                        break
                except:
                    continue

            if not username_field:
                logger.warning("Could not find username field")
                return

            # Find password field
            password_field = await page.query_selector("input[type='password']")
            if not password_field:
                logger.warning("Could not find password field")
                return

            # Fill and submit
            await username_field.fill(username)
            await password_field.fill(password)

            # Find and click submit button
            submit_button = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Login'), button:has-text('Sign In')")
            if submit_button:
                await submit_button.click()
                await page.wait_for_load_state("networkidle", timeout=5000)
                logger.info("Login successful")
            else:
                # Try pressing Enter
                await password_field.press("Enter")
                await page.wait_for_load_state("networkidle", timeout=5000)
                logger.info("Login submitted via Enter key")

        except Exception as e:
            logger.error(f"Login error: {e}")

    async def _is_logged_in(self, page: Page) -> bool:
        """Check if already logged in"""
        try:
            logout_button = await page.query_selector("button:has-text('Logout'), button:has-text('Sign Out'), a:has-text('Logout')")
            return bool(logout_button)
        except Exception:
            return False

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison"""
        # Remove fragment
        url = url.split("#")[0]
        # Remove trailing slash
        url = url.rstrip("/")
        return url

    def _is_same_domain(self, url: str) -> bool:
        """Check if URL is on same domain"""
        parsed = urlparse(url)
        return parsed.netloc == self.base_domain

    def _log_navigator_error(self, page_url: str, error_message: str):
        """Log navigator error to database"""
        try:
            self.supabase.table("navigator_errors").insert({
                "audit_session_id": self.audit_session_id,
                "error_type": "page_analysis_error",
                "error_message": error_message,
                "page_url": page_url,
            }).execute()
        except Exception as e:
            logger.error(f"Error logging navigator error: {e}")

    async def close(self):
        """Close browser and cleanup"""
        if self.browser:
            try:
                await self.browser.close()
                logger.info("Browser closed")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
