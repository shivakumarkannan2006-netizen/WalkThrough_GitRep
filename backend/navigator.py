"""
ShieldNavigator — Playwright-based browser automation with BFS traversal.

Architecture: Collect Everything First, Then Judge.
The navigator performs ALL browser interactions sequentially on each live page,
packages results into a PageBundle, closes the page, then returns bundles to
the crew for parallel stateless agent analysis.
"""

import asyncio
import base64
import io
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse
import uuid

import httpx
from PIL import Image, ImageChops
from playwright.async_api import BrowserContext, Page, async_playwright

from config import Settings, get_settings

logger = logging.getLogger(__name__)

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


async def smart_wait_idle(page: Page, settings: Settings) -> None:
    """Wait up to POST_LOAD_IDLE_MS after domcontentloaded; stop early when document is complete."""
    max_ms = settings.POST_LOAD_IDLE_MS
    step_ms = 150
    elapsed = 0
    while elapsed < max_ms:
        try:
            state = await page.evaluate("() => document.readyState")
            if state == "complete":
                await page.wait_for_timeout(min(300, max_ms - elapsed))
                return
        except Exception:
            pass
        await page.wait_for_timeout(step_ms)
        elapsed += step_ms


async def smart_goto(page: Page, url: str, settings: Settings) -> int:
    """Navigate with domcontentloaded + capped idle. Returns HTTP status (0 on failure)."""
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=settings.PAGE_LOAD_TIMEOUT_MS)
        await smart_wait_idle(page, settings)
        return resp.status if resp else 200
    except Exception as e:
        logger.error(f"smart_goto failed for {url}: {e}")
        return 0


async def smart_restore_page(page: Page, url: str, settings: Settings) -> None:
    """Faster restore after interaction tests (no long networkidle)."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=settings.PAGE_LOAD_TIMEOUT_MS)
        await smart_wait_idle(page, settings)
    except Exception as e:
        logger.debug(f"smart_restore_page failed for {url}: {e}")


# ---------------------------------------------------------------------------
# PageBundle — everything agents need, collected while browser is alive
# ---------------------------------------------------------------------------

@dataclass
class PageBundle:
    audit_page_id: str
    url: str
    page_title: str
    meta_description: str
    http_status_code: int
    load_time_ms: int
    authenticated: bool
    baseline_load_time_ms: Optional[int]

    # Accessibility
    axe_tree: Optional[Dict]

    # Raw content
    page_html: str
    page_text_blocks: List[str]

    # Screenshots — all compressed to max 1024px wide, JPEG 75
    screenshot_desktop_b64: str
    screenshot_mobile_b64: str
    screenshot_fout_b64: str

    # Security
    console_logs: List[Dict]
    cookies_on_load: List[Dict]

    # Layout
    viewport_overflow: Dict
    mobile_layout_shift_detected: bool

    # Interactive elements (visible only)
    interactive_element_bounding_boxes: List[Dict]

    # DOM mutations after load
    dom_mutations: List[Dict]

    # Links & media
    spa_route_urls: List[str]
    external_links: List[str]
    image_urls: List[str]

    # Business data
    prices_found: List[str]
    contact_info_found: List[str]
    testimonial_blocks: List[str]

    # Phase 2 — anchor click tests
    anchor_click_results: List[Dict]

    # Phase 3 — click timing tests
    click_interaction_timings: List[Dict]

    # Phase 4 — password field masking
    password_field_screenshots: List[Dict]

    # Phase 5 — form interaction tests
    form_interaction_results: List[Dict]

    # Phase 6 — persona simulations
    persona_frustrated_screenshot_b64: str
    persona_confused_hover_result: List[Dict]

    # Phase 7 — back button test (LAST)
    back_button_result: Dict


# ---------------------------------------------------------------------------
# Screenshot compression helper
# ---------------------------------------------------------------------------

def compress_screenshot(image_bytes: bytes, max_width: int = 1024, quality: int = 75) -> str:
    """Resize to max_width and encode as JPEG base64. Forces single-tile in Gemini."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        logger.error(f"compress_screenshot error: {e}")
        return ""


def _pillow_diff_significant(b64_a: str, b64_b: str, threshold: int = 10) -> bool:
    """Returns True if images differ significantly (pixel mean diff > threshold)."""
    try:
        if not b64_a or not b64_b:
            return False
        img_a = Image.open(io.BytesIO(base64.b64decode(b64_a))).convert("RGB")
        img_b = Image.open(io.BytesIO(base64.b64decode(b64_b))).convert("RGB")
        if img_a.size != img_b.size:
            img_b = img_b.resize(img_a.size, Image.LANCZOS)
        diff = ImageChops.difference(img_a, img_b)
        import statistics
        flat = list(diff.getdata())
        mean_diff = statistics.mean(v for pixel in flat for v in pixel)
        return mean_diff > threshold
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JavaScript snippets
# ---------------------------------------------------------------------------

_VISIBLE_INTERACTIVE_JS = """
() => Array.from(document.querySelectorAll(
    'button, a[href], input, select, textarea, [role="button"], [role="link"]'
)).filter(el =>
    getComputedStyle(el).display !== 'none' &&
    getComputedStyle(el).visibility !== 'hidden' &&
    el.offsetWidth > 0 &&
    el.offsetHeight > 0
).map(el => {
    const r = el.getBoundingClientRect();
    const tag = el.tagName.toLowerCase();
    const id = el.id ? '#' + el.id : '';
    const cls = el.className && typeof el.className === 'string'
        ? '.' + el.className.trim().split(/\\s+/)[0] : '';
    return { selector: tag + id + cls, x: r.x, y: r.y, width: r.width, height: r.height };
})
"""

_MUTATION_OBSERVER_JS = """
() => {
    window.__shieldMutations = [];
    const obs = new MutationObserver(mutations => {
        mutations.forEach(m => {
            window.__shieldMutations.push({
                type: m.type,
                selector: m.target.tagName ? m.target.tagName.toLowerCase() : 'unknown',
                added_nodes: m.addedNodes.length,
                removed_nodes: m.removedNodes.length,
            });
        });
    });
    obs.observe(document.body, { childList: true, subtree: true, attributes: true });
    window.__shieldObserver = obs;
}
"""

_COLLECT_MUTATIONS_JS = """
() => {
    if (window.__shieldObserver) window.__shieldObserver.disconnect();
    return window.__shieldMutations || [];
}
"""


# ---------------------------------------------------------------------------
# ShieldNavigator
# ---------------------------------------------------------------------------

class ShieldNavigator:
    """
    Autonomous browser navigator using Playwright with BFS traversal.
    Collects complete PageBundle per page before closing it.
    """

    def __init__(
        self,
        target_url: str,
        audit_session_id: str,
        supabase_client,
        credentials=None,
        broadcast_fn=None,
        stop_flag_fn=None,
        on_page_bundle: Optional[Callable[[PageBundle], Union[None, Awaitable[None]]]] = None,
    ):
        self.target_url = target_url
        self.audit_session_id = audit_session_id
        self.supabase = supabase_client
        self.credentials = credentials
        self.broadcast = broadcast_fn or (lambda x: None)
        self._stop_flag = stop_flag_fn or (lambda: False)
        self.on_page_bundle = on_page_bundle

        self.settings = get_settings()
        self.browser = None

        self.visited_unauth: set = set()
        self.visited_auth: set = set()
        self.pages_data = []
        self.base_domain = urlparse(target_url).netloc
        self.baseline_load_time = None
        self._traversal_start: float = 0.0
        self._bfs_timed_out = False
        self._preflight_cache: Dict[str, bool] = {}

    async def _emit(self, message: dict) -> None:
        """Invoke broadcast callback; supports sync and async handlers."""
        try:
            result = self.broadcast(message)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.debug(f"broadcast error: {e}")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def _bfs_time_exceeded(self) -> bool:
        if self._traversal_start <= 0:
            return False
        return (time.time() - self._traversal_start) >= self.settings.BFS_TIMEOUT_SECONDS

    async def start_traversal(self):
        try:
            self._traversal_start = time.time()
            logger.info(
                f"Starting traversal of {self.target_url} "
                f"(profile={self.settings.AUDIT_PROFILE})"
            )
            await self._emit({"type": "traversal_started", "target_url": self.target_url})

            async with async_playwright() as playwright:
                self.browser = await playwright.chromium.launch(
                    headless=self.settings.PLAYWRIGHT_HEADLESS,
                    args=self.settings.PLAYWRIGHT_ARGS,
                )

                unauth_context = await self.browser.new_context()
                auth_context = await self.browser.new_context() if self.credentials else None

                try:
                    await self._traverse_bfs(unauth_context, authenticated=False)
                    if auth_context and self.credentials:
                        await self._traverse_bfs(auth_context, authenticated=True)
                finally:
                    for ctx in [unauth_context, auth_context]:
                        if ctx:
                            try:
                                await ctx.close()
                            except Exception:
                                pass
                    try:
                        await self.browser.close()
                        self.browser = None
                    except Exception as e:
                        logger.error(f"Error closing browser: {e}")

            logger.info(
                f"Traversal complete. {len(self.pages_data)} pages collected."
                f"{' (BFS timeout)' if self._bfs_timed_out else ''}"
            )
            await self._emit({
                "type": "traversal_completed",
                "total_pages": len(self.pages_data),
                "bfs_timed_out": self._bfs_timed_out,
            })
            return self.pages_data

        except Exception as e:
            logger.error(f"Traversal error: {e}")
            await self._emit({"type": "traversal_error", "error": str(e)})
            raise

    # ------------------------------------------------------------------
    # BFS loop
    # ------------------------------------------------------------------

    async def _traverse_bfs(self, context, authenticated=False):
        enqueued = self.visited_auth if authenticated else self.visited_unauth
        queue = deque([self._normalize_url(self.target_url)])

        if self.settings.use_sitemap_seed():
            for u in await self._fetch_sitemap_urls():
                norm = self._normalize_url(u)
                if norm not in enqueued and self._is_same_domain(norm):
                    queue.append(norm)
                    enqueued.add(norm)

        visited_in_context: set = set()

        while queue and len(visited_in_context) < self.settings.MAX_PAGES_PER_AUDIT:
            if self._stop_flag():
                logger.info(f"BFS stopped by user at {len(visited_in_context)} pages")
                break
            if self._bfs_time_exceeded():
                self._bfs_timed_out = True
                logger.info(f"BFS stopped: exceeded {self.settings.BFS_TIMEOUT_SECONDS}s timeout")
                break

            current_url = queue.popleft()
            if current_url in visited_in_context:
                continue
            visited_in_context.add(current_url)

            logger.info(f"{'[AUTH]' if authenticated else '[UNAUTH]'} Visiting: {current_url}")

            page = await context.new_page()
            try:
                if authenticated and self.credentials and not await self._is_logged_in(page):
                    await self._pseudo_login(page, current_url)

                bundle = await self._collect_page_bundle(page, current_url, authenticated)

                if bundle:
                    self.pages_data.append(bundle)
                    if self.on_page_bundle:
                        result = self.on_page_bundle(bundle)
                        if asyncio.iscoroutine(result):
                            await result

                    new_urls = self._extract_links_from_html(bundle.page_html, current_url)
                    new_urls.extend(bundle.spa_route_urls or [])
                    for url in new_urls:
                        norm = self._normalize_url(url)
                        if (
                            norm not in visited_in_context
                            and norm not in enqueued
                            and self._is_same_domain(norm)
                            and len(visited_in_context) < self.settings.MAX_PAGES_PER_AUDIT
                        ):
                            if self.settings.ENABLE_HEAD_PREFLIGHT:
                                ok = await self._preflight_internal_url(norm)
                                if not ok:
                                    logger.debug(f"Skipping dead link (HEAD 404): {norm}")
                                    enqueued.add(norm)
                                    continue
                            queue.append(norm)
                            enqueued.add(norm)

            except Exception as e:
                logger.error(f"Error on {current_url}: {e}")
                self._log_error(current_url, str(e))
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

            await self._emit({
                "type": "page_discovered",
                "url": current_url,
                "authenticated": authenticated,
                "pages_discovered": len(self.pages_data),
            })

    # ------------------------------------------------------------------
    # Core collection — 7 phases, page handle destroyed after phase 7
    # ------------------------------------------------------------------

    async def _collect_page_bundle(self, page, url, authenticated):
        s = self.settings
        sw = s.SCREENSHOT_MAX_WIDTH
        sq = s.SCREENSHOT_JPEG_QUALITY

        # ----------------------------------------------------------------
        # Phase 1 — Passive collection (no state change)
        # ----------------------------------------------------------------
        console_logs = []
        page.on("console", lambda msg: console_logs.append({"type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda err: console_logs.append({"type": "pageerror", "text": str(err)}))

        # FOUT screenshot at commit (before fonts)
        screenshot_fout_b64 = ""
        try:
            await page.goto(url, wait_until="commit", timeout=s.PAGE_LOAD_TIMEOUT_MS)
            raw = await page.screenshot(full_page=True)
            screenshot_fout_b64 = compress_screenshot(raw, sw, sq)
        except Exception as e:
            logger.warning(f"FOUT screenshot failed for {url}: {e}")

        # Primary navigation — domcontentloaded + capped idle (faster than networkidle on SPAs)
        start_time = time.time()
        http_status_code = await smart_goto(page, url, s)
        load_time_ms = int((time.time() - start_time) * 1000)
        load_failed = http_status_code == 0
        if load_failed:
            self._log_error(url, "Primary page load failed (smart_goto returned status 0)")
        if self.baseline_load_time is None:
            self.baseline_load_time = load_time_ms
            logger.info(f"Baseline load time: {self.baseline_load_time}ms")

        # Cookies before any interaction
        cookies_on_load = []
        try:
            raw_cookies = await page.context.cookies()
            cookies_on_load = [{"name": c["name"], "domain": c.get("domain", "")} for c in raw_cookies]
        except Exception:
            pass

        # Inject MutationObserver
        try:
            await page.evaluate(_MUTATION_OBSERVER_JS)
        except Exception:
            pass

        # Desktop screenshot at 1280x900
        screenshot_desktop_b64 = ""
        screenshot_mobile_b64 = ""
        if s.ENABLE_SCREENSHOTS and not load_failed:
            try:
                await page.set_viewport_size({"width": 1280, "height": 900})
                raw = await page.screenshot(full_page=True)
                screenshot_desktop_b64 = compress_screenshot(raw, sw, sq)
            except Exception as e:
                logger.warning(f"Desktop screenshot failed for {url}: {e}")

            try:
                await page.set_viewport_size({"width": 375, "height": 812})
                await page.wait_for_timeout(300)
                raw = await page.screenshot(full_page=True)
                screenshot_mobile_b64 = compress_screenshot(raw, sw, sq)
                await page.set_viewport_size({"width": 1280, "height": 900})
            except Exception as e:
                logger.warning(f"Mobile screenshot failed for {url}: {e}")

        mobile_layout_shift_detected = _pillow_diff_significant(
            screenshot_desktop_b64, screenshot_mobile_b64, threshold=30
        )

        # Accessibility snapshot
        axe_tree = None
        try:
            axe_tree = await page.accessibility.snapshot()
        except Exception:
            pass

        # Page title and meta description
        page_title = ""
        meta_description = ""
        try:
            page_title = await page.title()
        except Exception:
            pass
        try:
            meta_description = await page.evaluate("""
                () => {
                    const el = document.querySelector('meta[name="description"]');
                    return el ? (el.getAttribute('content') || '').trim() : '';
                }
            """) or ""
        except Exception:
            pass

        # HTML
        page_html = ""
        try:
            page_html = await page.content()
        except Exception:
            pass

        # Text blocks
        page_text_blocks = []
        try:
            page_text_blocks = await page.evaluate("""
                () => Array.from(document.querySelectorAll('p, h1, h2, h3, h4'))
                    .map(el => el.innerText.trim()).filter(t => t.length > 10)
            """)
        except Exception:
            pass

        # Prices
        prices_found = []
        try:
            prices_found = await page.evaluate(r"""
                () => {
                    const text = document.body.innerText;
                    const matches = text.match(/[$€£¥][\d,]+\.?\d*/g) || [];
                    return [...new Set(matches)];
                }
            """)
        except Exception:
            pass

        # Contact info
        contact_info_found = []
        try:
            contact_info_found = await page.evaluate(r"""
                () => {
                    const text = document.body.innerText;
                    const emails = text.match(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g) || [];
                    const phones = text.match(/[+]?[(]?[0-9]{1,4}[)]?[\s\-.]?[(]?[0-9]{1,3}[)]?[\s\-.]?[0-9]{3,4}[\s\-.]?[0-9]{3,4}/g) || [];
                    return [...new Set([...emails, ...phones])];
                }
            """)
        except Exception:
            pass

        # Testimonials
        testimonial_blocks = []
        try:
            testimonial_blocks = await page.evaluate("""
                () => Array.from(document.querySelectorAll(
                    'blockquote, [class*="testimonial"], [class*="review"], [class*="quote"], [class*="feedback"]'
                )).map(el => el.innerText.trim()).filter(t => t.length > 20)
            """)
        except Exception:
            pass

        spa_route_urls = []
        try:
            spa_route_urls = await page.evaluate("""
                () => {
                    const out = new Set();
                    const add = (href) => {
                        try {
                            if (!href || href.startsWith('#') || href.startsWith('mailto:')) return;
                            out.add(new URL(href, location.href).href);
                        } catch (e) {}
                    };
                    document.querySelectorAll('[data-href]').forEach(el => add(el.getAttribute('data-href')));
                    document.querySelectorAll('a[href]').forEach(el => add(el.getAttribute('href')));
                    const nextData = document.getElementById('__NEXT_DATA__');
                    if (nextData && nextData.textContent) {
                        try {
                            const data = JSON.parse(nextData.textContent);
                            const page = data?.props?.pageProps?.slug || data?.query?.slug;
                            if (page) add('/' + page);
                        } catch (e) {}
                    }
                    return Array.from(out).slice(0, 40);
                }
            """) or []
        except Exception:
            pass

        # External links
        external_links = []
        try:
            bd = self.base_domain
            raw_ext = await page.evaluate(f"""
                () => Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(h => h.startsWith('http') && !h.includes('{bd}'))
                    .slice(0, 50)
            """)
            external_links = list(set(raw_ext))
        except Exception:
            pass

        # Image URLs
        image_urls = []
        try:
            image_urls = await page.evaluate("""
                () => Array.from(document.querySelectorAll('img[src]'))
                    .map(img => img.src)
                    .filter(s => s.startsWith('http') && !s.startsWith('data:'))
                    .slice(0, 30)
            """)
        except Exception:
            pass

        # Viewport overflow
        viewport_overflow = {"has_overflow": False, "scroll_width": 0, "window_width": 0}
        try:
            viewport_overflow = await page.evaluate("""
                () => ({
                    has_overflow: document.body.scrollWidth > window.innerWidth,
                    scroll_width: document.body.scrollWidth,
                    window_width: window.innerWidth,
                })
            """)
        except Exception:
            pass

        # Visible interactive element bounding boxes (with visibility filter)
        interactive_element_bounding_boxes = []
        try:
            interactive_element_bounding_boxes = await page.evaluate(_VISIBLE_INTERACTIVE_JS)
        except Exception:
            pass

        # Collect DOM mutations
        dom_mutations = []
        try:
            raw_mutations = await page.evaluate(_COLLECT_MUTATIONS_JS)
            dom_mutations = raw_mutations or []
        except Exception:
            pass

        run_interactions = s.run_interaction_phases() and not load_failed
        max_ctas = s.max_cta_clicks()
        max_forms = s.max_forms()
        max_form_inputs = s.max_form_input_types()
        max_hovers = s.max_hovers()
        max_anchors = s.max_anchor_tests()

        # ----------------------------------------------------------------
        # Phase 2 — Anchor click tests
        # ----------------------------------------------------------------
        anchor_click_results = []
        click_interaction_timings = []
        password_field_screenshots = []
        form_interaction_results = []
        persona_frustrated_screenshot_b64 = ""
        persona_confused_hover_result = []
        back_button_result = {"triggered": False, "result_url": "", "screenshot_b64": ""}

        if run_interactions:
            # Phase 2 — Anchor click tests
            if max_anchors > 0:
                try:
                    anchor_links = await page.evaluate(f"""
                        () => Array.from(document.querySelectorAll('a[href^="#"]'))
                            .map(a => a.getAttribute('href')).filter(Boolean).slice(0, {max_anchors})
                    """)
                    for href in anchor_links:
                        try:
                            scroll_before = await page.evaluate("() => window.scrollY")
                            await page.click(f'a[href="{href}"]')
                            await page.wait_for_timeout(500)
                            scroll_after = await page.evaluate("() => window.scrollY")
                            anchor_id = href.lstrip("#")
                            safe_id = anchor_id.replace("'", "\\'")
                            in_viewport = await page.evaluate(f"""
                                () => {{
                                    const el = document.getElementById('{safe_id}');
                                    if (!el) return false;
                                    const r = el.getBoundingClientRect();
                                    return r.top >= 0 && r.bottom <= window.innerHeight;
                                }}
                            """)
                            anchor_click_results.append({
                                "href": href,
                                "scroll_y_before": scroll_before,
                                "scroll_y_after": scroll_after,
                                "target_in_viewport": in_viewport,
                            })
                            await page.evaluate("() => window.scrollTo(0, 0)")
                        except Exception as e:
                            logger.debug(f"Anchor test {href}: {e}")
                except Exception:
                    pass

            # Phase 3 — Click timing tests
            if max_ctas > 0:
                try:
                    cta_selectors = await page.evaluate(f"""
                        () => Array.from(document.querySelectorAll('button, [role="button"]'))
                            .filter(el =>
                                getComputedStyle(el).display !== 'none' &&
                                el.offsetWidth > 0 && el.offsetHeight > 0
                            )
                            .slice(0, {max_ctas})
                            .map(el => {{
                                const tag = el.tagName.toLowerCase();
                                const id = el.id ? '#' + el.id : '';
                                return tag + id;
                            }})
                    """)
                    for sel in cta_selectors:
                        try:
                            t0 = time.time()
                            await page.click(sel, timeout=3000)
                            await smart_wait_idle(page, s)
                            response_ms = int((time.time() - t0) * 1000)
                            snap_b64 = ""
                            if s.ENABLE_SCREENSHOTS:
                                raw_snap = await page.screenshot()
                                snap_b64 = compress_screenshot(raw_snap, sw, sq)
                            click_interaction_timings.append({
                                "selector": sel,
                                "response_ms": response_ms,
                                "had_spinner": False,
                                "snapshot_b64": snap_b64,
                            })
                            await smart_restore_page(page, url, s)
                        except Exception as e:
                            logger.debug(f"Click timing {sel}: {e}")
                except Exception:
                    pass

            # Phase 4 — Password field masking
            try:
                pwd_selectors = await page.evaluate("""
                    () => Array.from(document.querySelectorAll(
                        'input[type="password"], input[name*="pin"], input[name*="secret"], ' +
                        'input[name*="ssn"], input[name*="card"], input[id*="pin"], input[id*="secret"]'
                    )).filter(el => el.offsetWidth > 0).map((el, i) => {
                        return el.id ? '#' + el.id : 'input:nth-of-type(' + (i+1) + ')';
                    })
                """)
                for sel in pwd_selectors[:5]:
                    try:
                        el = await page.query_selector(sel)
                        if el and s.ENABLE_SCREENSHOTS:
                            await el.fill("TestPassword123!")
                            raw_crop = await el.screenshot()
                            crop_b64 = compress_screenshot(raw_crop, sw, sq)
                            password_field_screenshots.append({
                                "selector": sel,
                                "screenshot_b64": crop_b64,
                            })
                            await el.fill("")
                    except Exception as e:
                        logger.debug(f"Password screenshot {sel}: {e}")
            except Exception:
                pass

            # Phase 5 — Form interaction tests
            if max_forms > 0 and max_form_inputs > 0:
                try:
                    form_selectors = await page.evaluate(f"""
                        () => Array.from(document.querySelectorAll('form'))
                            .filter(f => f.offsetWidth > 0)
                            .map((f, i) => f.id ? '#' + f.id : 'form:nth-of-type(' + (i+1) + ')')
                            .slice(0, {max_forms})
                    """)
                    test_inputs = [
                        ("empty", ""),
                        ("spacebar", "   "),
                        ("fake_email", "fake@fakefakedomain99.xyz"),
                    ][:max_form_inputs]

                    for form_sel in form_selectors:
                        for input_type, input_val in test_inputs:
                            try:
                                await smart_restore_page(page, url, s)
                                form = await page.query_selector(form_sel)
                                if not form:
                                    continue
                                pre_html_len = len(await page.content())
                                inputs = await form.query_selector_all(
                                    "input:not([type='hidden']):not([type='submit']):not([type='button'])"
                                )
                                for inp in inputs[:3]:
                                    inp_type = await inp.get_attribute("type") or "text"
                                    if inp_type in ("text", "email", "tel", "search", "url", ""):
                                        await inp.fill(input_val)
                                submit = await form.query_selector(
                                    "button[type='submit'], input[type='submit'], button:not([type])"
                                )
                                if submit:
                                    await submit.click()
                                elif inputs:
                                    await inputs[-1].press("Enter")
                                await page.wait_for_timeout(1000)
                                post_html = await page.content()
                                post_snap_b64 = ""
                                if s.ENABLE_SCREENSHOTS:
                                    raw_snap = await page.screenshot(full_page=True)
                                    post_snap_b64 = compress_screenshot(raw_snap, sw, sq)
                                form_interaction_results.append({
                                    "form_selector": form_sel,
                                    "input_type": input_type,
                                    "pre_html_len": pre_html_len,
                                    "post_html": post_html,
                                    "post_screenshot_b64": post_snap_b64,
                                })
                            except Exception as e:
                                logger.debug(f"Form test {form_sel}/{input_type}: {e}")
                except Exception:
                    pass

                try:
                    await smart_restore_page(page, url, s)
                except Exception:
                    pass

            # Phase 6 — Persona simulations
            if s.ENABLE_PERSONAS and max_hovers > 0:
                try:
                    cta = await page.query_selector("button, [role='button']")
                    if cta:
                        for _ in range(5):
                            try:
                                await cta.click(timeout=1000)
                            except Exception:
                                pass
                            await page.wait_for_timeout(100)
                        if s.ENABLE_SCREENSHOTS:
                            raw = await page.screenshot(full_page=True)
                            persona_frustrated_screenshot_b64 = compress_screenshot(raw, sw, sq)
                except Exception as e:
                    logger.debug(f"Frustrated persona {url}: {e}")

                try:
                    await smart_restore_page(page, url, s)
                except Exception:
                    pass

                try:
                    interactive_selectors = await page.evaluate(f"""
                        () => Array.from(document.querySelectorAll('button, a[href], [role="button"]'))
                            .filter(el => el.offsetWidth > 0 && el.offsetHeight > 0)
                            .slice(0, {max_hovers})
                            .map(el => {{
                                const tag = el.tagName.toLowerCase();
                                const id = el.id ? '#' + el.id : '';
                                return tag + id;
                            }})
                    """)
                    for sel in interactive_selectors:
                        try:
                            el = await page.query_selector(sel)
                            if el:
                                await el.hover(timeout=2000)
                                await page.wait_for_timeout(800)
                                safe_sel = sel.replace("'", "\\'")
                                has_tooltip = await page.evaluate(f"""
                                    () => {{
                                        const el = document.querySelector('{safe_sel}');
                                        if (!el) return false;
                                        return !!(el.title || el.getAttribute('aria-label') ||
                                            document.querySelector('[role="tooltip"]'));
                                    }}
                                """)
                                persona_confused_hover_result.append({
                                    "selector": sel,
                                    "tooltip_found": has_tooltip,
                                })
                        except Exception:
                            pass
                except Exception:
                    pass

            # Phase 7 — Back button test (LAST)
            try:
                bd = self.base_domain
                first_internal_link = await page.evaluate(f"""
                    () => {{
                        const links = Array.from(document.querySelectorAll('a[href]'))
                            .map(a => a.href)
                            .filter(h => h.startsWith('http') && h.includes('{bd}')
                                && h !== window.location.href);
                        return links[0] || null;
                    }}
                """)
                if first_internal_link:
                    await smart_goto(page, first_internal_link, s)
                    await page.go_back(wait_until="domcontentloaded", timeout=8000)
                    await smart_wait_idle(page, s)
                    result_url = page.url
                    back_b64 = ""
                    if s.ENABLE_SCREENSHOTS:
                        raw = await page.screenshot(full_page=True)
                        back_b64 = compress_screenshot(raw, sw, sq)
                    back_button_result = {
                        "triggered": True,
                        "result_url": result_url,
                        "screenshot_b64": back_b64,
                    }
            except Exception as e:
                logger.debug(f"Back button test {url}: {e}")

        # ----------------------------------------------------------------
        # Persist to Supabase
        # ----------------------------------------------------------------
        audit_page_id = str(uuid.uuid4())
        try:
            resp = self.supabase.table("audit_pages").insert({
                "audit_session_id": self.audit_session_id,
                "url": url,
                "http_status_code": http_status_code,
                "load_time_ms": load_time_ms,
                "is_accessible_without_auth": not authenticated,
                "page_title": page_title,
            }).execute()
            if resp.data:
                audit_page_id = resp.data[0]["id"]

            self.supabase.table("audit_page_snapshots").insert({
                "audit_page_id": audit_page_id,
                "axe_tree_json": axe_tree or {},
                "page_title": page_title,
            }).execute()
        except Exception as e:
            logger.error(f"Supabase persist error for {url}: {e}")

        if (
            self.baseline_load_time is not None
            and load_time_ms > self.baseline_load_time + s.PERFORMANCE_BASELINE_THRESHOLD_MS
        ):
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

        return PageBundle(
            audit_page_id=audit_page_id,
            url=url,
            page_title=page_title,
            meta_description=meta_description,
            http_status_code=http_status_code,
            load_time_ms=load_time_ms,
            authenticated=authenticated,
            baseline_load_time_ms=self.baseline_load_time,
            axe_tree=axe_tree,
            page_html=page_html,
            page_text_blocks=page_text_blocks,
            screenshot_desktop_b64=screenshot_desktop_b64,
            screenshot_mobile_b64=screenshot_mobile_b64,
            screenshot_fout_b64=screenshot_fout_b64,
            console_logs=console_logs,
            cookies_on_load=cookies_on_load,
            viewport_overflow=viewport_overflow,
            mobile_layout_shift_detected=mobile_layout_shift_detected,
            interactive_element_bounding_boxes=interactive_element_bounding_boxes,
            dom_mutations=dom_mutations,
            spa_route_urls=spa_route_urls,
            external_links=external_links,
            image_urls=image_urls,
            prices_found=prices_found,
            contact_info_found=contact_info_found,
            testimonial_blocks=testimonial_blocks,
            anchor_click_results=anchor_click_results,
            click_interaction_timings=click_interaction_timings,
            password_field_screenshots=password_field_screenshots,
            form_interaction_results=form_interaction_results,
            persona_frustrated_screenshot_b64=persona_frustrated_screenshot_b64,
            persona_confused_hover_result=persona_confused_hover_result,
            back_button_result=back_button_result,
        )

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    async def _pseudo_login(self, page, target_url):
        if not self.credentials or not self.credentials[0]:
            return
        username, password = self.credentials
        try:
            await smart_goto(page, target_url, self.settings)
            field = None
            for sel in ["input[type='email']", "input[name*='email']", "input[name*='username']", "input[type='text']"]:
                field = await page.query_selector(sel)
                if field:
                    break
            pwd = await page.query_selector("input[type='password']")
            if not field or not pwd:
                return
            await field.fill(username)
            await pwd.fill(password)
            submit = await page.query_selector("button[type='submit'], input[type='submit']")
            if submit:
                await submit.click()
            else:
                await pwd.press("Enter")
            await smart_wait_idle(page, self.settings)
        except Exception as e:
            logger.error(f"Login error: {e}")

    async def _is_logged_in(self, page) -> bool:
        try:
            btn = await page.query_selector(
                "button:has-text('Logout'), button:has-text('Sign Out'), a:has-text('Logout')"
            )
            return bool(btn)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # URL utilities
    # ------------------------------------------------------------------

    def _extract_links_from_html(self, html: str, base_url: str):
        from bs4 import BeautifulSoup
        urls = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all("a", href=True):
                href = tag["href"]
                if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                    continue
                urls.append(urljoin(base_url, href))
            for tag in soup.find_all(attrs={"data-href": True}):
                href = tag.get("data-href", "")
                if href and not href.startswith("#"):
                    urls.append(urljoin(base_url, href))
            for tag in soup.find_all("link", rel=True):
                rel = " ".join(tag.get("rel", [])).lower()
                if "canonical" in rel and tag.get("href"):
                    urls.append(urljoin(base_url, tag["href"]))
        except Exception:
            pass
        return urls

    async def _fetch_sitemap_urls(self) -> List[str]:
        """Seed BFS from sitemap.xml (deep profile)."""
        if not self.settings.use_sitemap_seed():
            return []
        parsed = urlparse(self.target_url)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        urls: List[str] = []
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
                resp = await client.get(sitemap_url)
                if resp.status_code >= 400:
                    return []
                root = ET.fromstring(resp.text)
                for loc in root.findall(".//sm:loc", SITEMAP_NS):
                    if loc.text and self._is_same_domain(loc.text):
                        urls.append(loc.text)
                if not urls:
                    for loc in root.findall(".//{*}loc"):
                        if loc.text and self._is_same_domain(loc.text):
                            urls.append(loc.text)
        except Exception as e:
            logger.debug(f"Sitemap fetch failed for {sitemap_url}: {e}")
        return urls[: self.settings.SITEMAP_MAX_URLS]

    async def _preflight_internal_url(self, url: str) -> bool:
        if url in self._preflight_cache:
            return self._preflight_cache[url]
        ok = True
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=5.0) as client:
                resp = await client.head(url)
                ok = resp.status_code < 400
        except Exception:
            ok = True
        self._preflight_cache[url] = ok
        return ok

    def _normalize_url(self, url: str) -> str:
        return url.split("#")[0].rstrip("/")

    def _is_same_domain(self, url: str) -> bool:
        return urlparse(url).netloc == self.base_domain

    def _log_error(self, page_url: str, error_message: str):
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
        if self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
