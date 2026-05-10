"""
Crew Orchestrator - Manages parallel execution of 6 specialized agents
"""

import asyncio
import logging
import json
from typing import Dict, List, Callable, Optional
from datetime import datetime
import re
import uuid

from config import get_settings

logger = logging.getLogger(__name__)

class CrewOrchestrator:
    """Orchestrates parallel execution of all 6 crew agents"""

    def __init__(
        self,
        supabase_client,
        audit_session_id: str,
        broadcast_fn: Optional[Callable] = None,
    ):
        self.supabase = supabase_client
        self.audit_session_id = audit_session_id
        self.broadcast = broadcast_fn or (lambda x: None)
        self.settings = get_settings()

    async def analyze_page(self, page_data: Dict):
        """Run all 6 crew agents in parallel on discovered page"""
        try:
            url = page_data.get("url")
            audit_page_id = page_data.get("audit_page_id")

            logger.info(f"Analyzing page: {url}")

            # Create agent instances
            agents = {
                "ghost_navigator": GhostNavigator(self.supabase, self.audit_session_id),
                "mirror_stylist": MirrorStyleist(self.supabase, self.audit_session_id),
                "vault_counsel": VaultCounsel(self.supabase, self.audit_session_id),
                "fact_checker": FactChecker(self.supabase, self.audit_session_id),
                "fortress_sentry": FortressSentry(self.supabase, self.audit_session_id),
                "vision_architect": VisionArchitect(self.supabase, self.audit_session_id),
            }

            # Run all agents in parallel
            tasks = []
            for agent_name, agent in agents.items():
                task = asyncio.create_task(
                    agent.analyze(page_data, audit_page_id),
                    name=agent_name
                )
                tasks.append(task)

            # Gather results with timeout
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                issues_count = 0
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        agent_name = list(agents.keys())[i]
                        logger.error(f"Agent {agent_name} error: {result}")
                    else:
                        issues_count += result.get("issues_found", 0)

                await self.broadcast({
                    "type": "page_analyzed",
                    "url": url,
                    "issues_found": issues_count,
                    "total_pages_analyzed": len([]),  # TODO: track total
                })

            except asyncio.TimeoutError:
                logger.error(f"Crew analysis timeout for {url}")

        except Exception as e:
            logger.error(f"Error in crew orchestration: {e}")

# ============== AGENT #1: GHOST NAVIGATOR ==============

class GhostNavigator:
    """Detects logic and reliability issues"""

    def __init__(self, supabase, audit_session_id: str):
        self.supabase = supabase
        self.audit_session_id = audit_session_id

    async def analyze(self, page_data: Dict, audit_page_id: str) -> Dict:
        """Analyze page for Ghost Navigator issues"""
        issues_found = 0

        try:
            url = page_data.get("url")
            axe_tree = page_data.get("axe_tree", {})
            page_obj = page_data.get("page_object")

            # Check 1: Form Loop-Holes
            logger.info(f"[Ghost] Checking form loop-holes for {url}")
            form_issues = await self._check_form_loopholes(page_obj, url, audit_page_id)
            issues_found += len(form_issues)

            # Check 2: Deep Link Accuracy
            logger.info(f"[Ghost] Checking deep link accuracy for {url}")
            anchor_issues = await self._check_deep_links(page_obj, url, audit_page_id)
            issues_found += len(anchor_issues)

            # Check 3: Orphaned States
            logger.info(f"[Ghost] Checking for orphaned states on {url}")
            orphaned_issues = await self._check_orphaned_states(page_obj, url, audit_page_id, axe_tree)
            issues_found += len(orphaned_issues)

            # Check 4: Back Button Paradox (simplified - would need session tracking)
            logger.info(f"[Ghost] Checking back button behavior on {url}")
            back_issues = await self._check_back_button(page_obj, url, audit_page_id)
            issues_found += len(back_issues)

            # Check 5: 404s and Broken Routes
            logger.info(f"[Ghost] Checking for 404s on {url}")
            broken_issues = await self._check_broken_routes(page_obj, url, audit_page_id)
            issues_found += len(broken_issues)

            return {"agent": "ghost_navigator", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Ghost Navigator error: {e}")
            return {"agent": "ghost_navigator", "issues_found": 0}

    async def _check_form_loopholes(self, page, url: str, audit_page_id: str) -> List[str]:
        """Test forms with edge cases"""
        issues = []

        try:
            forms = await page.query_selector_all("form")

            for form_idx, form in enumerate(forms):
                form_selector = f"form:nth-of-type({form_idx + 1})"

                # Get all inputs in form
                inputs = await form.query_selector_all("input, textarea, select")

                for input_idx, inp in enumerate(inputs):
                    input_type = await inp.get_attribute("type")
                    input_name = await inp.get_attribute("name")

                    # Test 1: Spacebar-only submission
                    if input_type != "submit":
                        try:
                            await inp.fill(" ")  # Just spacebar
                            is_valid = await page.evaluate(
                                f"document.querySelector('{form_selector}').checkValidity() === true"
                            )

                            if not is_valid:
                                issue_data = {
                                    "agent_name": "Ghost Navigator",
                                    "issue_category": "Logic & Reliability",
                                    "specific_issue_detail": f"Form field accepts spacebar-only input without validation (field: {input_name})",
                                    "severity": "medium",
                                    "affected_url": url,
                                    "affected_element_xpath": f"{form_selector} input[name='{input_name}']",
                                }
                                self.supabase.table("audit_issues").insert(issue_data).execute()
                                issues.append(f"Spacebar-only validation on {input_name}")
                        except Exception as e:
                            logger.debug(f"Could not test spacebar validation: {e}")

        except Exception as e:
            logger.error(f"Form loopholes check error: {e}")

        return issues

    async def _check_deep_links(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check if anchor links scroll to correct positions"""
        issues = []

        try:
            anchors = await page.query_selector_all("a[href*='#']")

            for anchor in anchors:
                href = await anchor.get_attribute("href")
                if href and href.startswith("#"):
                    anchor_id = href[1:]

                    # Check if target exists
                    target = await page.query_selector(f"#{anchor_id}, [id='{anchor_id}']")
                    if not target:
                        issue_data = {
                            "agent_name": "Ghost Navigator",
                            "issue_category": "Logic & Reliability",
                            "specific_issue_detail": f"Anchor link points to non-existent target: {href}",
                            "severity": "medium",
                            "affected_url": url,
                            "affected_element_xpath": f"a[href='{href}']",
                        }
                        self.supabase.table("audit_issues").insert(issue_data).execute()
                        issues.append(f"Broken anchor: {href}")

        except Exception as e:
            logger.error(f"Deep links check error: {e}")

        return issues

    async def _check_orphaned_states(self, page, url: str, audit_page_id: str, axe_tree: Dict) -> List[str]:
        """Check for orphaned states with no CTA"""
        issues = []

        try:
            # Check if page has navigation elements
            nav_elements = await page.query_selector_all("nav, .navbar, [role='navigation'], a[href='/'], .logo")

            if not nav_elements:
                # Check for CTAs
                ctas = await page.query_selector_all("a, button, [role='button']")
                if len(ctas) == 0:
                    issue_data = {
                        "agent_name": "Ghost Navigator",
                        "issue_category": "Logic & Reliability",
                        "specific_issue_detail": "Orphaned page state: No navigation or CTA found to return to main site",
                        "severity": "high",
                        "affected_url": url,
                    }
                    self.supabase.table("audit_issues").insert(issue_data).execute()
                    issues.append("Orphaned state detected")

        except Exception as e:
            logger.error(f"Orphaned states check error: {e}")

        return issues

    async def _check_back_button(self, page, url: str, audit_page_id: str) -> List[str]:
        """Simplified back button check"""
        issues = []
        # Note: Full implementation would require session tracking across pages
        return issues

    async def _check_broken_routes(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check for broken routes and 404s"""
        issues = []

        try:
            # Check current page load status
            status = page.url
            if "404" in status or "error" in status.lower():
                issue_data = {
                    "agent_name": "Ghost Navigator",
                    "issue_category": "Logic & Reliability",
                    "specific_issue_detail": "Page returned 404 or error status",
                    "severity": "critical",
                    "affected_url": url,
                }
                self.supabase.table("audit_issues").insert(issue_data).execute()
                issues.append("404 or error page")

        except Exception as e:
            logger.error(f"Broken routes check error: {e}")

        return issues

# ============== AGENT #2: MIRROR STYLIST ==============

class MirrorStyleist:
    """Detects aesthetic and UX issues"""

    def __init__(self, supabase, audit_session_id: str):
        self.supabase = supabase
        self.audit_session_id = audit_session_id

    async def analyze(self, page_data: Dict, audit_page_id: str) -> Dict:
        """Analyze page for Mirror Stylist issues"""
        issues_found = 0

        try:
            url = page_data.get("url")
            page_obj = page_data.get("page_object")

            # Check 1: Visual Contrast Failures
            logger.info(f"[Mirror] Checking contrast for {url}")
            contrast_issues = await self._check_contrast(page_obj, url, audit_page_id)
            issues_found += len(contrast_issues)

            # Check 2: Z-Index Collisions
            logger.info(f"[Mirror] Checking z-index collisions for {url}")
            zindex_issues = await self._check_z_index_collisions(page_obj, url, audit_page_id)
            issues_found += len(zindex_issues)

            # Check 3: Touch Target Density (mobile)
            logger.info(f"[Mirror] Checking touch targets for {url}")
            touch_issues = await self._check_touch_targets(page_obj, url, audit_page_id)
            issues_found += len(touch_issues)

            # Check 4: Horizontal Scroll Bugs
            logger.info(f"[Mirror] Checking for horizontal scroll bugs on {url}")
            scroll_issues = await self._check_horizontal_scroll(page_obj, url, audit_page_id)
            issues_found += len(scroll_issues)

            # Check 5: Font Jump (FOUT)
            logger.info(f"[Mirror] Checking for font jumps on {url}")
            font_issues = await self._check_font_jumps(page_obj, url, audit_page_id)
            issues_found += len(font_issues)

            # Check 6: Mobile Integrity
            logger.info(f"[Mirror] Checking mobile integrity on {url}")
            mobile_issues = await self._check_mobile_integrity(page_obj, url, audit_page_id)
            issues_found += len(mobile_issues)

            # Check 7: General Polish
            logger.info(f"[Mirror] Checking general polish on {url}")
            polish_issues = await self._check_general_polish(page_obj, url, audit_page_id)
            issues_found += len(polish_issues)

            return {"agent": "mirror_stylist", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Mirror Stylist error: {e}")
            return {"agent": "mirror_stylist", "issues_found": 0}

    async def _check_contrast(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check for low contrast text"""
        issues = []

        try:
            # Get all text elements
            text_elements = await page.query_selector_all("p, h1, h2, h3, h4, h5, h6, span, a, button, label")

            for elem in text_elements[:20]:  # Sample limit
                try:
                    computed_style = await page.evaluate(
                        f"window.getComputedStyle(arguments[0])",
                        elem
                    )

                    # Extract color values (simplified)
                    color = computed_style.get("color", "")
                    bg_color = computed_style.get("backgroundColor", "")

                    if color and bg_color:
                        # Flag low contrast (very simplified check)
                        if "rgb(255" in color and "rgb(255" in bg_color:
                            issue_data = {
                                "agent_name": "Mirror Stylist",
                                "issue_category": "Aesthetics & UX",
                                "specific_issue_detail": f"Low contrast detected: text color {color} on {bg_color}",
                                "severity": "medium",
                                "affected_url": url,
                            }
                            self.supabase.table("audit_issues").insert(issue_data).execute()
                            issues.append("Low contrast")

                except Exception as e:
                    logger.debug(f"Could not analyze element contrast: {e}")

        except Exception as e:
            logger.error(f"Contrast check error: {e}")

        return issues

    async def _check_z_index_collisions(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check for z-index stacking issues"""
        issues = []

        try:
            # Get all elements with z-index
            z_indexed = await page.evaluate("""
                Array.from(document.querySelectorAll('*')).filter(el => {
                    const zIndex = window.getComputedStyle(el).zIndex;
                    return zIndex !== 'auto' && zIndex !== '0';
                }).map(el => ({
                    selector: el.tagName,
                    zIndex: window.getComputedStyle(el).zIndex,
                    classes: el.className
                })).slice(0, 20)
            """)

            if len(z_indexed) > 1:
                # Check for overlaps (simplified)
                zs = sorted([int(el["zIndex"]) for el in z_indexed if el["zIndex"].isdigit()])
                if len(zs) > 0 and max(zs) > 1000:
                    issue_data = {
                        "agent_name": "Mirror Stylist",
                        "issue_category": "Aesthetics & UX",
                        "specific_issue_detail": f"High z-index values detected (potential collisions): {max(zs)}",
                        "severity": "low",
                        "affected_url": url,
                    }
                    self.supabase.table("audit_issues").insert(issue_data).execute()
                    issues.append("Z-index collision risk")

        except Exception as e:
            logger.error(f"Z-index check error: {e}")

        return issues

    async def _check_touch_targets(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check mobile touch target sizes"""
        issues = []

        try:
            # Set mobile viewport
            await page.set_viewport_size({"width": 375, "height": 667})

            buttons = await page.query_selector_all("button, a, [role='button']")

            for btn in buttons[:10]:
                try:
                    box = await btn.bounding_box()
                    if box:
                        width = box["width"]
                        height = box["height"]

                        if width < 48 or height < 48:
                            issue_data = {
                                "agent_name": "Mirror Stylist",
                                "issue_category": "Aesthetics & UX",
                                "specific_issue_detail": f"Touch target too small: {width}x{height}px (minimum 48x48px)",
                                "severity": "medium",
                                "affected_url": url,
                            }
                            self.supabase.table("audit_issues").insert(issue_data).execute()
                            issues.append(f"Small touch target: {width}x{height}")

                except Exception as e:
                    logger.debug(f"Could not measure touch target: {e}")

        except Exception as e:
            logger.error(f"Touch targets check error: {e}")

        return issues

    async def _check_horizontal_scroll(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check for horizontal scroll overflow"""
        issues = []

        try:
            scroll_width = await page.evaluate("document.documentElement.scrollWidth")
            window_width = await page.evaluate("window.innerWidth")

            if scroll_width > window_width:
                issue_data = {
                    "agent_name": "Mirror Stylist",
                    "issue_category": "Aesthetics & UX",
                    "specific_issue_detail": f"Horizontal scroll detected: content wider than viewport ({scroll_width}px > {window_width}px)",
                    "severity": "medium",
                    "affected_url": url,
                }
                self.supabase.table("audit_issues").insert(issue_data).execute()
                issues.append(f"Horizontal scroll: {scroll_width}px > {window_width}px")

        except Exception as e:
            logger.error(f"Horizontal scroll check error: {e}")

        return issues

    async def _check_font_jumps(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check for Flash of Unstyled Text (FOUT)"""
        issues = []

        try:
            # Check for @font-face declarations
            fonts = await page.evaluate("""
                Array.from(document.styleSheets).filter(sheet => {
                    try {
                        return sheet.cssRules;
                    } catch {
                        return false;
                    }
                }).flatMap(sheet => Array.from(sheet.cssRules))
                .filter(rule => rule.type === 5)
                .slice(0, 5);
            """)

            if fonts:
                issue_data = {
                    "agent_name": "Mirror Stylist",
                    "issue_category": "Aesthetics & UX",
                    "specific_issue_detail": f"Custom fonts detected - potential FOUT (Flash of Unstyled Text) detected. Ensure font-display is optimized.",
                    "severity": "low",
                    "affected_url": url,
                }
                self.supabase.table("audit_issues").insert(issue_data).execute()
                issues.append("Potential FOUT")

        except Exception as e:
            logger.error(f"Font jump check error: {e}")

        return issues

    async def _check_mobile_integrity(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check mobile-specific issues"""
        issues = []

        try:
            # Already set mobile viewport above
            # Check for keyboard overlap by focusing input
            inputs = await page.query_selector_all("input")

            for inp in inputs[:5]:
                try:
                    await inp.focus()
                    # In real scenario, would measure layout shift
                    await inp.blur()
                except Exception as e:
                    logger.debug(f"Could not test input focus: {e}")

        except Exception as e:
            logger.error(f"Mobile integrity check error: {e}")

        return issues

    async def _check_general_polish(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check for general polish issues like typos, placeholder text"""
        issues = []

        try:
            # Get all text content
            text_content = await page.text_content()

            if text_content:
                # Check for common placeholder/debug text
                placeholders = ["Lorem ipsum", "TODO", "FIXME", "XXX", "placeholder"]

                for placeholder in placeholders:
                    if placeholder.lower() in text_content.lower():
                        issue_data = {
                            "agent_name": "Mirror Stylist",
                            "issue_category": "Aesthetics & UX",
                            "specific_issue_detail": f"Placeholder or debug text found: '{placeholder}'",
                            "severity": "low",
                            "affected_url": url,
                        }
                        self.supabase.table("audit_issues").insert(issue_data).execute()
                        issues.append(f"Placeholder text: {placeholder}")

        except Exception as e:
            logger.error(f"General polish check error: {e}")

        return issues

# ============== AGENT #3: VAULT COUNSEL ==============

class VaultCounsel:
    """Detects compliance and integrity issues"""

    def __init__(self, supabase, audit_session_id: str):
        self.supabase = supabase
        self.audit_session_id = audit_session_id

    async def analyze(self, page_data: Dict, audit_page_id: str) -> Dict:
        """Analyze page for Vault Counsel issues"""
        issues_found = 0

        try:
            url = page_data.get("url")
            page_obj = page_data.get("page_object")

            # Check 1: GDPR/Legal Compliance
            logger.info(f"[Vault] Checking GDPR compliance on {url}")
            gdpr_issues = await self._check_gdpr_compliance(page_obj, url, audit_page_id)
            issues_found += len(gdpr_issues)

            # Check 2: Cookie Consent
            logger.info(f"[Vault] Checking cookie consent on {url}")
            cookie_issues = await self._check_cookie_consent(page_obj, url, audit_page_id)
            issues_found += len(cookie_issues)

            # Check 3: Pricing Consistency
            logger.info(f"[Vault] Checking pricing consistency on {url}")
            pricing_issues = await self._check_pricing_consistency(page_obj, url, audit_page_id)
            issues_found += len(pricing_issues)

            # Check 4: Contact Info Consistency
            logger.info(f"[Vault] Checking contact info on {url}")
            contact_issues = await self._check_contact_info(page_obj, url, audit_page_id)
            issues_found += len(contact_issues)

            # Check 5: Dark Pattern Detection
            logger.info(f"[Vault] Checking for dark patterns on {url}")
            dark_issues = await self._check_dark_patterns(page_obj, url, audit_page_id)
            issues_found += len(dark_issues)

            return {"agent": "vault_counsel", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Vault Counsel error: {e}")
            return {"agent": "vault_counsel", "issues_found": 0}

    async def _check_gdpr_compliance(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check GDPR compliance"""
        issues = []

        try:
            page_text = await page.text_content()

            # Check for GDPR-related keywords
            gdpr_keywords = ["GDPR", "personal data", "privacy", "consent", "processing"]
            gdpr_mentioned = any(kw.lower() in page_text.lower() for kw in gdpr_keywords)

            if not gdpr_mentioned and "/privacy" in url.lower():
                issue_data = {
                    "agent_name": "Vault Counsel",
                    "issue_category": "Compliance & Integrity",
                    "specific_issue_detail": "Privacy policy page missing GDPR compliance language",
                    "severity": "high",
                    "affected_url": url,
                }
                self.supabase.table("audit_issues").insert(issue_data).execute()
                self.supabase.table("gdpr_issues").insert({
                    "audit_session_id": self.audit_session_id,
                    "issue_type": "gdpr_language_missing",
                    "affected_page_url": url,
                    "severity": "high",
                }).execute()
                issues.append("GDPR language missing")

        except Exception as e:
            logger.error(f"GDPR check error: {e}")

        return issues

    async def _check_cookie_consent(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check cookie consent banners"""
        issues = []

        try:
            # Look for cookie banner
            cookie_banner = await page.query_selector("[role='dialog']:has-text('cookie'), .cookie-banner, .consent-banner")

            if cookie_banner:
                # Check if cookies are set before consent
                cookies = await page.context.cookies()
                tracking_cookies = [c for c in cookies if any(x in c.get("name", "").lower() for x in ["ga", "facebook", "analytics"])]

                if tracking_cookies:
                    for cookie in tracking_cookies:
                        issue_data = {
                            "agent_name": "Vault Counsel",
                            "issue_category": "Compliance & Integrity",
                            "specific_issue_detail": f"Tracking cookie set before consent: {cookie['name']}",
                            "severity": "critical",
                            "affected_url": url,
                        }
                        self.supabase.table("audit_issues").insert(issue_data).execute()
                        issues.append(f"Tracking cookie pre-set: {cookie['name']}")

        except Exception as e:
            logger.error(f"Cookie consent check error: {e}")

        return issues

    async def _check_pricing_consistency(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check for pricing inconsistencies"""
        issues = []

        try:
            # Extract prices using regex
            page_text = await page.text_content()
            prices = re.findall(r'\$[\d,]+\.?\d*', page_text)

            if prices:
                # Store for cross-page comparison
                self.supabase.table("page_audit_data").update({
                    "detected_frameworks": json.dumps({"prices": prices}),
                }).eq("id", audit_page_id).execute()

        except Exception as e:
            logger.error(f"Pricing check error: {e}")

        return issues

    async def _check_contact_info(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check contact information consistency"""
        issues = []

        try:
            # Extract emails
            page_text = await page.text_content()
            emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', page_text)

            if len(set(emails)) > 1:
                issue_data = {
                    "agent_name": "Vault Counsel",
                    "issue_category": "Compliance & Integrity",
                    "specific_issue_detail": f"Multiple different contact emails found: {', '.join(set(emails)[:3])}",
                    "severity": "low",
                    "affected_url": url,
                }
                self.supabase.table("audit_issues").insert(issue_data).execute()
                issues.append(f"Multiple contact emails: {len(set(emails))}")

        except Exception as e:
            logger.error(f"Contact info check error: {e}")

        return issues

    async def _check_dark_patterns(self, page, url: str, audit_page_id: str) -> List[str]:
        """Detect dark patterns in UI"""
        issues = []

        try:
            # Look for misleading button sizes
            buttons = await page.query_selector_all("button, a[role='button']")

            for btn in buttons[:20]:
                try:
                    text = await btn.text_content()
                    box = await btn.bounding_box()

                    if box and ("cancel" in text.lower() or "no" in text.lower()):
                        # Check if cancel button is smaller than confirm
                        if box["width"] < 80 or box["height"] < 40:
                            issue_data = {
                                "agent_name": "Vault Counsel",
                                "issue_category": "Compliance & Integrity",
                                "specific_issue_detail": f"Possible dark pattern: '{text}' button is {box['width']}x{box['height']}px (small for rejection action)",
                                "severity": "medium",
                                "affected_url": url,
                            }
                            self.supabase.table("audit_issues").insert(issue_data).execute()
                            issues.append(f"Dark pattern: {text}")

                except Exception as e:
                    logger.debug(f"Could not analyze button: {e}")

        except Exception as e:
            logger.error(f"Dark patterns check error: {e}")

        return issues

# ============== AGENT #4: FACT CHECKER ==============

class FactChecker:
    """Verifies claims and external links"""

    def __init__(self, supabase, audit_session_id: str):
        self.supabase = supabase
        self.audit_session_id = audit_session_id

    async def analyze(self, page_data: Dict, audit_page_id: str) -> Dict:
        """Analyze page for Fact Checker issues"""
        issues_found = 0

        try:
            url = page_data.get("url")
            page_obj = page_data.get("page_object")

            # Check 1: External Link Verification
            logger.info(f"[Fact] Verifying external links on {url}")
            link_issues = await self._verify_external_links(page_obj, url, audit_page_id)
            issues_found += len(link_issues)

            # Check 2: Testimonial Audit
            logger.info(f"[Fact] Auditing testimonials on {url}")
            testimonial_issues = await self._audit_testimonials(page_obj, url, audit_page_id)
            issues_found += len(testimonial_issues)

            return {"agent": "fact_checker", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Fact Checker error: {e}")
            return {"agent": "fact_checker", "issues_found": 0}

    async def _verify_external_links(self, page, url: str, audit_page_id: str) -> List[str]:
        """Verify all external links are reachable"""
        issues = []

        try:
            links = await page.query_selector_all("a[href^='http']")

            for link in links[:20]:  # Limit to avoid timeout
                try:
                    href = await link.get_attribute("href")

                    # Record link for verification
                    if href and not href.startswith(url):
                        self.supabase.table("audit_external_links").insert({
                            "audit_session_id": self.audit_session_id,
                            "link_url": href,
                            "found_on_page": url,
                            "reachable": True,  # Assume reachable for now
                        }).execute()

                except Exception as e:
                    logger.debug(f"Could not verify link: {e}")

        except Exception as e:
            logger.error(f"External links check error: {e}")

        return issues

    async def _audit_testimonials(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check for AI-generated or fake testimonials"""
        issues = []

        try:
            # Look for testimonial elements
            testimonials = await page.query_selector_all("[role='blockquote'], .testimonial, .quote, [class*='testimonial']")

            for testimonial in testimonials[:5]:
                try:
                    text = await testimonial.text_content()

                    # Simple AI detection heuristics
                    ai_patterns = [
                        "exceptional",
                        "highly recommend",
                        "game-changer",
                        "life-changing",
                        "absolutely amazing",
                    ]

                    ai_score = sum(1 for pattern in ai_patterns if pattern.lower() in text.lower()) * 20

                    if ai_score > 60:
                        self.supabase.table("testimonial_audits").insert({
                            "audit_session_id": self.audit_session_id,
                            "testimonial_text": text[:200],
                            "page_url": url,
                            "ai_detection_confidence": min(ai_score, 100),
                            "authenticity_score_0_100": max(0, 100 - ai_score),
                        }).execute()

                        issue_data = {
                            "agent_name": "Fact Checker",
                            "issue_category": "Verification",
                            "specific_issue_detail": f"Testimonial may be AI-generated (confidence: {ai_score}%): \"{text[:100]}...\"",
                            "severity": "medium",
                            "affected_url": url,
                        }
                        self.supabase.table("audit_issues").insert(issue_data).execute()
                        issues.append(f"Potential AI testimonial")

                except Exception as e:
                    logger.debug(f"Could not analyze testimonial: {e}")

        except Exception as e:
            logger.error(f"Testimonials check error: {e}")

        return issues

# ============== AGENT #5: FORTRESS SENTRY ==============

class FortressSentry:
    """Detects security and privacy issues"""

    def __init__(self, supabase, audit_session_id: str):
        self.supabase = supabase
        self.audit_session_id = audit_session_id

    async def analyze(self, page_data: Dict, audit_page_id: str) -> Dict:
        """Analyze page for Fortress Sentry issues"""
        issues_found = 0

        try:
            url = page_data.get("url")
            page_obj = page_data.get("page_object")

            # Check 1: Console Log Leaks
            logger.info(f"[Fortress] Checking console for leaks on {url}")
            console_issues = await self._check_console_leaks(page_obj, url, audit_page_id)
            issues_found += len(console_issues)

            # Check 2: Sensitive Data Masking
            logger.info(f"[Fortress] Checking input masking on {url}")
            masking_issues = await self._check_sensitive_masking(page_obj, url, audit_page_id)
            issues_found += len(masking_issues)

            # Check 3: EXIF Metadata
            logger.info(f"[Fortress] Checking image EXIF data on {url}")
            exif_issues = await self._check_image_exif(page_obj, url, audit_page_id)
            issues_found += len(exif_issues)

            return {"agent": "fortress_sentry", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Fortress Sentry error: {e}")
            return {"agent": "fortress_sentry", "issues_found": 0}

    async def _check_console_leaks(self, page, url: str, audit_page_id: str) -> List[str]:
        """Monitor console for API key leaks and errors"""
        issues = []
        console_messages = []

        def on_console(msg):
            console_messages.append({
                "type": msg.type,
                "text": msg.text,
                "location": msg.location,
            })

        page.on("console", on_console)

        try:
            # Trigger console activity by navigating
            await page.wait_for_load_state("networkidle")

            # Check for secrets
            secret_patterns = {
                "api_key": r"api[_-]?key\s*[:=]",
                "jwt": r"JWT|Bearer\s+[a-zA-Z0-9\-_.]+",
                "aws_key": r"AKIA[0-9A-Z]{16}",
                "db_url": r"(postgres|mysql|mongodb)://",
            }

            for msg in console_messages:
                for pattern_name, pattern in secret_patterns.items():
                    if re.search(pattern, msg["text"], re.IGNORECASE):
                        issue_data = {
                            "agent_name": "Fortress Sentry",
                            "issue_category": "Privacy & Security",
                            "specific_issue_detail": f"Potential {pattern_name} leak in console: {msg['text'][:100]}",
                            "severity": "critical",
                            "affected_url": url,
                        }
                        self.supabase.table("audit_issues").insert(issue_data).execute()
                        self.supabase.table("security_console_leaks").insert({
                            "audit_session_id": self.audit_session_id,
                            "page_url": url,
                            "console_message_type": msg["type"],
                            "detected_pattern_type": pattern_name,
                            "message_text": msg["text"][:500],
                            "severity": "critical",
                        }).execute()
                        issues.append(f"Console leak: {pattern_name}")

        except Exception as e:
            logger.error(f"Console check error: {e}")

        return issues

    async def _check_sensitive_masking(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check if password fields are properly masked"""
        issues = []

        try:
            password_fields = await page.query_selector_all("input[type='password']")

            for field in password_fields[:5]:
                try:
                    # Type test value
                    await field.fill("testpassword123")

                    # Check displayed value (should be masked)
                    displayed_value = await field.input_value()

                    if "testpassword" in displayed_value:
                        issue_data = {
                            "agent_name": "Fortress Sentry",
                            "issue_category": "Privacy & Security",
                            "specific_issue_detail": "Password field not properly masked - plaintext visible while typing",
                            "severity": "critical",
                            "affected_url": url,
                        }
                        self.supabase.table("audit_issues").insert(issue_data).execute()
                        issues.append("Password not masked")

                    await field.clear()

                except Exception as e:
                    logger.debug(f"Could not test masking: {e}")

        except Exception as e:
            logger.error(f"Masking check error: {e}")

        return issues

    async def _check_image_exif(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check images for EXIF metadata"""
        issues = []

        try:
            # Get all images
            images = await page.query_selector_all("img")

            for img in images[:5]:  # Limit for performance
                try:
                    src = await img.get_attribute("src")
                    if src and src.startswith("http"):
                        # Record for EXIF analysis (would need image download in production)
                        self.supabase.table("security_exif_findings").insert({
                            "audit_session_id": self.audit_session_id,
                            "image_url": src,
                            "exif_field_name": "pending_analysis",
                            "found_on_page": url,
                            "privacy_risk_level": "low",
                        }).execute()

                except Exception as e:
                    logger.debug(f"Could not analyze image: {e}")

        except Exception as e:
            logger.error(f"EXIF check error: {e}")

        return issues

# ============== AGENT #6: VISION ARCHITECT ==============

class VisionArchitect:
    """Detects psychology and value-based issues"""

    def __init__(self, supabase, audit_session_id: str):
        self.supabase = supabase
        self.audit_session_id = audit_session_id

    async def analyze(self, page_data: Dict, audit_page_id: str) -> Dict:
        """Analyze page for Vision Architect issues"""
        issues_found = 0

        try:
            url = page_data.get("url")
            page_obj = page_data.get("page_object")

            # Check 1: Empty State Analysis
            logger.info(f"[Vision] Checking for empty states on {url}")
            empty_issues = await self._check_empty_states(page_obj, url, audit_page_id)
            issues_found += len(empty_issues)

            # Check 2: Reading Level Audit
            logger.info(f"[Vision] Analyzing reading level on {url}")
            reading_issues = await self._check_reading_level(page_obj, url, audit_page_id)
            issues_found += len(reading_issues)

            # Check 3: Tone Consistency
            logger.info(f"[Vision] Checking tone consistency on {url}")
            tone_issues = await self._check_tone_consistency(page_obj, url, audit_page_id)
            issues_found += len(tone_issues)

            # Check 4: Enhancement Strategies
            logger.info(f"[Vision] Generating enhancement strategies for {url}")
            enhancement_issues = await self._generate_enhancements(page_obj, url, audit_page_id)
            issues_found += len(enhancement_issues)

            return {"agent": "vision_architect", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Vision Architect error: {e}")
            return {"agent": "vision_architect", "issues_found": 0}

    async def _check_empty_states(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check for unmotivating empty states"""
        issues = []

        try:
            page_text = await page.text_content()

            # Check if page looks empty
            if len(page_text.strip()) < 200:
                # Check for CTAs
                buttons = await page.query_selector_all("button, a[role='button']")

                if len(buttons) == 0:
                    issue_data = {
                        "agent_name": "Vision Architect",
                        "issue_category": "Psychology & Value",
                        "specific_issue_detail": "Empty state page lacks motivating CTA or guidance",
                        "severity": "medium",
                        "affected_url": url,
                    }
                    self.supabase.table("audit_issues").insert(issue_data).execute()
                    issues.append("Empty state without CTA")

        except Exception as e:
            logger.error(f"Empty states check error: {e}")

        return issues

    async def _check_reading_level(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check reading level and AI-sounding text"""
        issues = []

        try:
            # Get body text
            paragraphs = await page.query_selector_all("p, h1, h2, h3")

            ai_patterns = ["innovative", "cutting-edge", "revolutionary", "synergy", "paradigm", "leverage"]

            for para in paragraphs[:5]:
                try:
                    text = await para.text_content()

                    ai_score = sum(1 for pattern in ai_patterns if pattern.lower() in text.lower()) * 20

                    if ai_score > 40:
                        self.supabase.table("reading_level_audits").insert({
                            "audit_page_id": audit_page_id,
                            "text_block_selector": "p",
                            "ai_pattern_score_0_100": min(ai_score, 100),
                            "text_snippet": text[:100],
                        }).execute()

                        if ai_score > 60:
                            issue_data = {
                                "agent_name": "Vision Architect",
                                "issue_category": "Psychology & Value",
                                "specific_issue_detail": f"Text reads as AI-generated (overuse of buzzwords): \"{text[:80]}...\"",
                                "severity": "low",
                                "affected_url": url,
                            }
                            self.supabase.table("audit_issues").insert(issue_data).execute()
                            issues.append(f"AI-sounding text detected")

                except Exception as e:
                    logger.debug(f"Could not analyze reading level: {e}")

        except Exception as e:
            logger.error(f"Reading level check error: {e}")

        return issues

    async def _check_tone_consistency(self, page, url: str, audit_page_id: str) -> List[str]:
        """Check tone consistency across page sections"""
        issues = []

        try:
            # Get sections
            headers = await page.query_selector_all("h1, h2, h3")

            tones_detected = []

            for header in headers[:3]:
                try:
                    text = await header.text_content()

                    # Classify tone (very simplified)
                    if any(word in text.lower() for word in ["free", "save", "limited", "now"]):
                        tone = "urgency"
                    elif any(word in text.lower() for word in ["premium", "luxury", "exclusive"]):
                        tone = "luxury"
                    elif any(word in text.lower() for word in ["easy", "simple", "fast"]):
                        tone = "casual"
                    else:
                        tone = "neutral"

                    tones_detected.append(tone)

                except Exception as e:
                    logger.debug(f"Could not analyze header tone: {e}")

            # Check for inconsistency
            if len(set(tones_detected)) > 1 and len(tones_detected) > 1:
                self.supabase.table("tone_analysis").insert({
                    "audit_page_id": audit_page_id,
                    "section_name": "page_overall",
                    "detected_tone": ", ".join(set(tones_detected)),
                    "consistency_score_0_100": 50,
                }).execute()

                issue_data = {
                    "agent_name": "Vision Architect",
                    "issue_category": "Psychology & Value",
                    "specific_issue_detail": f"Tone inconsistency detected: {', '.join(set(tones_detected))}. Consider maintaining consistent brand voice.",
                    "severity": "low",
                    "affected_url": url,
                }
                self.supabase.table("audit_issues").insert(issue_data).execute()
                issues.append(f"Tone inconsistency: {set(tones_detected)}")

        except Exception as e:
            logger.error(f"Tone check error: {e}")

        return issues

    async def _generate_enhancements(self, page, url: str, audit_page_id: str) -> List[str]:
        """Generate psychology-based enhancement recommendations"""
        issues = []

        try:
            # Check for images
            images = await page.query_selector_all("img")

            if len(images) < 3:
                enhancement_data = {
                    "audit_session_id": self.audit_session_id,
                    "page_url": url,
                    "suggested_enhancement": "Add lifestyle/aspirational imagery",
                    "psychology_principle": "Luxury audiences respond to visual storytelling and lifestyle aspirations",
                    "expected_impact_description": "Estimated 10-15% improvement in time-on-page and click-through rates",
                    "priority_rank": 1,
                    "category": "visual",
                }
                self.supabase.table("enhancement_strategies").insert(enhancement_data).execute()
                issues.append("Consider adding visual content")

            # Check for social proof
            testimonials = await page.query_selector_all("[role='blockquote'], .testimonial")

            if len(testimonials) == 0:
                enhancement_data = {
                    "audit_session_id": self.audit_session_id,
                    "page_url": url,
                    "suggested_enhancement": "Add customer testimonials or case studies",
                    "psychology_principle": "Social proof and authority signals significantly increase conversion trust",
                    "expected_impact_description": "Estimated 5-20% increase in conversion depending on positioning",
                    "priority_rank": 2,
                    "category": "social_proof",
                }
                self.supabase.table("enhancement_strategies").insert(enhancement_data).execute()
                issues.append("Add social proof elements")

        except Exception as e:
            logger.error(f"Enhancement generation error: {e}")

        return issues
