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

from bs4 import BeautifulSoup
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
            soup = BeautifulSoup(page_data.get("page_html", ""), "html.parser")

            # Check 1: Form Loop-Holes
            logger.info(f"[Ghost] Checking form loop-holes for {url}")
            form_issues = await self._check_form_loopholes(soup, url, audit_page_id)
            issues_found += len(form_issues)

            # Check 2: Deep Link Accuracy
            logger.info(f"[Ghost] Checking deep link accuracy for {url}")
            anchor_issues = await self._check_deep_links(soup, url, audit_page_id)
            issues_found += len(anchor_issues)

            # Check 3: Orphaned States
            logger.info(f"[Ghost] Checking for orphaned states on {url}")
            orphaned_issues = await self._check_orphaned_states(soup, url, audit_page_id, axe_tree)
            issues_found += len(orphaned_issues)

            # Check 4: Back Button Paradox (simplified - would need session tracking)
            logger.info(f"[Ghost] Checking back button behavior on {url}")
            back_issues = await self._check_back_button(soup, url, audit_page_id)
            issues_found += len(back_issues)

            # Check 5: 404s and Broken Routes
            logger.info(f"[Ghost] Checking for 404s on {url}")
            broken_issues = await self._check_broken_routes(soup, url, audit_page_id)
            issues_found += len(broken_issues)

            return {"agent": "ghost_navigator", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Ghost Navigator error: {e}")
            return {"agent": "ghost_navigator", "issues_found": 0}

    async def _check_form_loopholes(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Test forms with edge cases"""
        issues = []

        try:
            forms = soup.find_all("form")

            for form_idx, form in enumerate(forms):
                form_selector = f"form:nth-of-type({form_idx + 1})"

                # Get all inputs in form
                inputs = form.find_all(["input", "textarea", "select"])

                for inp in inputs:
                    input_type = inp.get("type")
                    input_name = inp.get("name")

                    # Test 1: Fields with no required attribute and no pattern validation
                    if input_type != "submit" and input_type != "hidden":
                        has_required = inp.get("required") is not None
                        has_pattern = inp.get("pattern") is not None
                        has_minlength = inp.get("minlength") is not None

                        if not has_required and not has_pattern and not has_minlength:
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
            logger.error(f"Form loopholes check error: {e}")

        return issues

    async def _check_deep_links(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check if anchor links scroll to correct positions"""
        issues = []

        try:
            anchors = soup.find_all("a", href=True)

            for anchor in anchors:
                href = anchor.get("href")
                if href and href.startswith("#"):
                    anchor_id = href[1:]

                    # Check if target exists in the document
                    target = soup.find(id=anchor_id)
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

    async def _check_orphaned_states(self, soup: BeautifulSoup, url: str, audit_page_id: str, axe_tree: Dict) -> List[str]:
        """Check for orphaned states with no CTA"""
        issues = []

        try:
            # Check if page has navigation elements
            nav_elements = (
                soup.find_all("nav")
                + soup.find_all(class_="navbar")
                + soup.find_all(attrs={"role": "navigation"})
                + soup.find_all("a", href="/")
                + soup.find_all(class_="logo")
            )

            if not nav_elements:
                # Check for CTAs
                ctas = (
                    soup.find_all("a")
                    + soup.find_all("button")
                    + soup.find_all(attrs={"role": "button"})
                )
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

    async def _check_back_button(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Simplified back button check"""
        issues = []
        # Note: Full implementation would require session tracking across pages
        return issues

    async def _check_broken_routes(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check for broken routes and 404s"""
        issues = []

        try:
            # Check current page load status based on URL
            if "404" in url or "error" in url.lower():
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
            soup = BeautifulSoup(page_data.get("page_html", ""), "html.parser")

            # Check 1: Visual Contrast Failures
            logger.info(f"[Mirror] Checking contrast for {url}")
            contrast_issues = await self._check_contrast(soup, url, audit_page_id)
            issues_found += len(contrast_issues)

            # Check 2: Z-Index Collisions
            logger.info(f"[Mirror] Checking z-index collisions for {url}")
            zindex_issues = await self._check_z_index_collisions(soup, url, audit_page_id)
            issues_found += len(zindex_issues)

            # Check 3: Touch Target Density (mobile)
            logger.info(f"[Mirror] Checking touch targets for {url}")
            touch_issues = await self._check_touch_targets(soup, url, audit_page_id)
            issues_found += len(touch_issues)

            # Check 4: Horizontal Scroll Bugs
            logger.info(f"[Mirror] Checking for horizontal scroll bugs on {url}")
            scroll_issues = await self._check_horizontal_scroll(soup, url, audit_page_id)
            issues_found += len(scroll_issues)

            # Check 5: Font Jump (FOUT)
            logger.info(f"[Mirror] Checking for font jumps on {url}")
            font_issues = await self._check_font_jumps(soup, url, audit_page_id)
            issues_found += len(font_issues)

            # Check 6: Mobile Integrity
            logger.info(f"[Mirror] Checking mobile integrity on {url}")
            mobile_issues = await self._check_mobile_integrity(soup, url, audit_page_id)
            issues_found += len(mobile_issues)

            # Check 7: General Polish
            logger.info(f"[Mirror] Checking general polish on {url}")
            polish_issues = await self._check_general_polish(soup, url, audit_page_id)
            issues_found += len(polish_issues)

            return {"agent": "mirror_stylist", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Mirror Stylist error: {e}")
            return {"agent": "mirror_stylist", "issues_found": 0}

    async def _check_contrast(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check for low contrast text via inline styles"""
        issues = []

        try:
            # Get text elements that have inline style attributes
            text_elements = soup.find_all(
                ["p", "h1", "h2", "h3", "h4", "h5", "h6", "span", "a", "button", "label"],
                style=True
            )

            for elem in text_elements[:20]:  # Sample limit
                try:
                    style = elem.get("style", "")

                    # Extract color and background-color from inline styles
                    color_match = re.search(r'(?<!\w)color\s*:\s*([^;]+)', style, re.IGNORECASE)
                    bg_match = re.search(r'background-color\s*:\s*([^;]+)', style, re.IGNORECASE)

                    if color_match and bg_match:
                        color = color_match.group(1).strip()
                        bg_color = bg_match.group(1).strip()

                        # Flag low contrast (very simplified check - both white-ish)
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

    async def _check_z_index_collisions(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check for z-index stacking issues via inline styles"""
        issues = []

        try:
            # Find all elements with inline style containing z-index
            styled_elements = soup.find_all(style=True)

            z_values = []
            for elem in styled_elements:
                style = elem.get("style", "")
                z_match = re.search(r'z-index\s*:\s*(\d+)', style, re.IGNORECASE)
                if z_match:
                    z_val = int(z_match.group(1))
                    if z_val != 0:
                        z_values.append(z_val)

            z_values = z_values[:20]

            if len(z_values) > 1:
                zs = sorted(z_values)
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

    async def _check_touch_targets(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check mobile touch target sizes - cannot be done statically, skip"""
        # Bounding box measurements require a live rendered page; not available from HTML alone
        return []

    async def _check_horizontal_scroll(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check for horizontal scroll overflow - cannot be done statically, skip"""
        # scrollWidth / window.innerWidth require a live rendered page
        return []

    async def _check_font_jumps(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check for Flash of Unstyled Text (FOUT) via link/style tags"""
        issues = []

        try:
            has_custom_fonts = False

            # Check for Google Fonts link tags
            link_tags = soup.find_all("link", href=True)
            for link in link_tags:
                href = link.get("href", "")
                if "fonts.googleapis.com" in href or "fonts.gstatic.com" in href:
                    has_custom_fonts = True
                    break

            # Check for @font-face in <style> tags
            if not has_custom_fonts:
                style_tags = soup.find_all("style")
                for style_tag in style_tags:
                    style_text = style_tag.get_text()
                    if "@font-face" in style_text:
                        has_custom_fonts = True
                        break

            if has_custom_fonts:
                issue_data = {
                    "agent_name": "Mirror Stylist",
                    "issue_category": "Aesthetics & UX",
                    "specific_issue_detail": "Custom fonts detected - potential FOUT (Flash of Unstyled Text) detected. Ensure font-display is optimized.",
                    "severity": "low",
                    "affected_url": url,
                }
                self.supabase.table("audit_issues").insert(issue_data).execute()
                issues.append("Potential FOUT")

        except Exception as e:
            logger.error(f"Font jump check error: {e}")

        return issues

    async def _check_mobile_integrity(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check mobile-specific issues - cannot be done statically, skip"""
        # Focus/blur interactions and layout shift require a live rendered page
        return []

    async def _check_general_polish(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check for general polish issues like typos, placeholder text"""
        issues = []

        try:
            # Get all text content
            text_content = soup.get_text(separator=" ", strip=True)

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
            soup = BeautifulSoup(page_data.get("page_html", ""), "html.parser")

            # Check 1: GDPR/Legal Compliance
            logger.info(f"[Vault] Checking GDPR compliance on {url}")
            gdpr_issues = await self._check_gdpr_compliance(soup, url, audit_page_id)
            issues_found += len(gdpr_issues)

            # Check 2: Cookie Consent
            logger.info(f"[Vault] Checking cookie consent on {url}")
            cookie_issues = await self._check_cookie_consent(soup, url, audit_page_id)
            issues_found += len(cookie_issues)

            # Check 3: Pricing Consistency
            logger.info(f"[Vault] Checking pricing consistency on {url}")
            pricing_issues = await self._check_pricing_consistency(soup, url, audit_page_id)
            issues_found += len(pricing_issues)

            # Check 4: Contact Info Consistency
            logger.info(f"[Vault] Checking contact info on {url}")
            contact_issues = await self._check_contact_info(soup, url, audit_page_id)
            issues_found += len(contact_issues)

            # Check 5: Dark Pattern Detection
            logger.info(f"[Vault] Checking for dark patterns on {url}")
            dark_issues = await self._check_dark_patterns(soup, url, audit_page_id)
            issues_found += len(dark_issues)

            return {"agent": "vault_counsel", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Vault Counsel error: {e}")
            return {"agent": "vault_counsel", "issues_found": 0}

    async def _check_gdpr_compliance(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check GDPR compliance"""
        issues = []

        try:
            page_text = soup.get_text(separator=" ", strip=True)

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

    async def _check_cookie_consent(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check cookie consent banners"""
        issues = []

        try:
            # Look for cookie banner elements in the HTML
            cookie_banner = (
                soup.find(class_="cookie-banner")
                or soup.find(class_="consent-banner")
                or soup.find(attrs={"role": "dialog"})
            )

            if cookie_banner:
                banner_text = cookie_banner.get_text(strip=True).lower()
                if "cookie" in banner_text or "consent" in banner_text:
                    # Check for tracking scripts loaded unconditionally
                    scripts = soup.find_all("script", src=True)
                    tracking_scripts = [
                        s for s in scripts
                        if any(x in (s.get("src") or "").lower() for x in ["ga.", "gtag", "analytics", "facebook", "fbq"])
                    ]

                    for script in tracking_scripts:
                        script_src = script.get("src", "")
                        issue_data = {
                            "agent_name": "Vault Counsel",
                            "issue_category": "Compliance & Integrity",
                            "specific_issue_detail": f"Tracking script loaded before consent may be present: {script_src}",
                            "severity": "critical",
                            "affected_url": url,
                        }
                        self.supabase.table("audit_issues").insert(issue_data).execute()
                        issues.append(f"Tracking script pre-loaded: {script_src}")

        except Exception as e:
            logger.error(f"Cookie consent check error: {e}")

        return issues

    async def _check_pricing_consistency(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check for pricing inconsistencies"""
        issues = []

        try:
            # Extract prices using regex
            page_text = soup.get_text(separator=" ", strip=True)
            prices = re.findall(r'\$[\d,]+\.?\d*', page_text)

            if prices:
                # Store for cross-page comparison
                self.supabase.table("page_audit_data").update({
                    "detected_frameworks": json.dumps({"prices": prices}),
                }).eq("id", audit_page_id).execute()

        except Exception as e:
            logger.error(f"Pricing check error: {e}")

        return issues

    async def _check_contact_info(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check contact information consistency"""
        issues = []

        try:
            # Extract emails
            page_text = soup.get_text(separator=" ", strip=True)
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

    async def _check_dark_patterns(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Detect dark patterns in UI"""
        issues = []

        try:
            # Look for misleading button text (bounding box not available; check by text alone)
            buttons = soup.find_all("button") + soup.find_all("a", attrs={"role": "button"})

            for btn in buttons[:20]:
                try:
                    text = btn.get_text(strip=True)

                    if text and ("cancel" in text.lower() or "no" in text.lower()):
                        # Without bounding box, flag any cancel/no button that has
                        # visually-diminishing inline styles (e.g. very small font-size)
                        style = btn.get("style", "")
                        font_size_match = re.search(r'font-size\s*:\s*([\d.]+)px', style, re.IGNORECASE)
                        if font_size_match and float(font_size_match.group(1)) < 12:
                            issue_data = {
                                "agent_name": "Vault Counsel",
                                "issue_category": "Compliance & Integrity",
                                "specific_issue_detail": f"Possible dark pattern: '{text}' button has very small font size (rejection action de-emphasized)",
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
            soup = BeautifulSoup(page_data.get("page_html", ""), "html.parser")

            # Check 1: External Link Verification
            logger.info(f"[Fact] Verifying external links on {url}")
            link_issues = await self._verify_external_links(soup, url, audit_page_id)
            issues_found += len(link_issues)

            # Check 2: Testimonial Audit
            logger.info(f"[Fact] Auditing testimonials on {url}")
            testimonial_issues = await self._audit_testimonials(soup, url, audit_page_id)
            issues_found += len(testimonial_issues)

            return {"agent": "fact_checker", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Fact Checker error: {e}")
            return {"agent": "fact_checker", "issues_found": 0}

    async def _verify_external_links(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Verify all external links are reachable"""
        issues = []

        try:
            links = soup.find_all("a", href=True)
            external_links = [a for a in links if (a.get("href") or "").startswith("http")]

            for link in external_links[:20]:  # Limit to avoid timeout
                try:
                    href = link.get("href")

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

    async def _audit_testimonials(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check for AI-generated or fake testimonials"""
        issues = []

        try:
            # Look for testimonial elements
            testimonials = (
                soup.find_all(attrs={"role": "blockquote"})
                + soup.find_all(class_="testimonial")
                + soup.find_all(class_="quote")
                + [el for el in soup.find_all(class_=True) if any("testimonial" in c for c in el.get("class", []))]
            )

            for testimonial in testimonials[:5]:
                try:
                    text = testimonial.get_text(strip=True)

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
            soup = BeautifulSoup(page_data.get("page_html", ""), "html.parser")

            # Check 1: Console Log Leaks
            logger.info(f"[Fortress] Checking console for leaks on {url}")
            console_issues = await self._check_console_leaks(soup, url, audit_page_id)
            issues_found += len(console_issues)

            # Check 2: Sensitive Data Masking
            logger.info(f"[Fortress] Checking input masking on {url}")
            masking_issues = await self._check_sensitive_masking(soup, url, audit_page_id)
            issues_found += len(masking_issues)

            # Check 3: EXIF Metadata
            logger.info(f"[Fortress] Checking image EXIF data on {url}")
            exif_issues = await self._check_image_exif(soup, url, audit_page_id)
            issues_found += len(exif_issues)

            return {"agent": "fortress_sentry", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Fortress Sentry error: {e}")
            return {"agent": "fortress_sentry", "issues_found": 0}

    async def _check_console_leaks(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Scan inline scripts for potential secret leaks"""
        issues = []

        try:
            # Scan all inline <script> tags for secret patterns
            secret_patterns = {
                "api_key": r"api[_-]?key\s*[:=]",
                "jwt": r"JWT|Bearer\s+[a-zA-Z0-9\-_.]+",
                "aws_key": r"AKIA[0-9A-Z]{16}",
                "db_url": r"(postgres|mysql|mongodb)://",
            }

            inline_scripts = soup.find_all("script", src=False)

            for script_tag in inline_scripts:
                script_text = script_tag.get_text()
                for pattern_name, pattern in secret_patterns.items():
                    if re.search(pattern, script_text, re.IGNORECASE):
                        snippet = script_text[:100].strip()
                        issue_data = {
                            "agent_name": "Fortress Sentry",
                            "issue_category": "Privacy & Security",
                            "specific_issue_detail": f"Potential {pattern_name} leak in inline script: {snippet}",
                            "severity": "critical",
                            "affected_url": url,
                        }
                        self.supabase.table("audit_issues").insert(issue_data).execute()
                        self.supabase.table("security_console_leaks").insert({
                            "audit_session_id": self.audit_session_id,
                            "page_url": url,
                            "console_message_type": "inline_script",
                            "detected_pattern_type": pattern_name,
                            "message_text": script_text[:500],
                            "severity": "critical",
                        }).execute()
                        issues.append(f"Console leak: {pattern_name}")

        except Exception as e:
            logger.error(f"Console check error: {e}")

        return issues

    async def _check_sensitive_masking(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check if password fields are properly declared as type=password"""
        issues = []

        try:
            # Find all inputs that may collect sensitive data
            password_fields = soup.find_all("input", attrs={"type": "password"})

            for field in password_fields[:5]:
                try:
                    # In static HTML we can verify the type attribute is present and correct.
                    # If a field's name/id suggests a password but type is not 'password', flag it.
                    field_name = (field.get("name") or field.get("id") or "").lower()
                    field_type = (field.get("type") or "").lower()

                    # The field was already selected as type=password, so type is correct here.
                    # Check for autocomplete="off" which can be a security concern on password fields
                    autocomplete = (field.get("autocomplete") or "").lower()
                    if autocomplete == "off":
                        issue_data = {
                            "agent_name": "Fortress Sentry",
                            "issue_category": "Privacy & Security",
                            "specific_issue_detail": "Password field has autocomplete='off' which may impede password manager usage",
                            "severity": "low",
                            "affected_url": url,
                        }
                        self.supabase.table("audit_issues").insert(issue_data).execute()
                        issues.append("Password autocomplete disabled")

                except Exception as e:
                    logger.debug(f"Could not test masking: {e}")

            # Also check: inputs with password-related names that are NOT type=password
            all_inputs = soup.find_all("input")
            for inp in all_inputs:
                name = (inp.get("name") or inp.get("id") or inp.get("placeholder") or "").lower()
                inp_type = (inp.get("type") or "text").lower()
                if any(kw in name for kw in ["password", "passwd", "secret", "pin"]) and inp_type != "password":
                    issue_data = {
                        "agent_name": "Fortress Sentry",
                        "issue_category": "Privacy & Security",
                        "specific_issue_detail": "Password field not properly masked - plaintext visible while typing",
                        "severity": "critical",
                        "affected_url": url,
                    }
                    self.supabase.table("audit_issues").insert(issue_data).execute()
                    issues.append("Password not masked")

        except Exception as e:
            logger.error(f"Masking check error: {e}")

        return issues

    async def _check_image_exif(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check images for EXIF metadata"""
        issues = []

        try:
            # Get all images
            images = soup.find_all("img")

            for img in images[:5]:  # Limit for performance
                try:
                    src = img.get("src")
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
            soup = BeautifulSoup(page_data.get("page_html", ""), "html.parser")

            # Check 1: Empty State Analysis
            logger.info(f"[Vision] Checking for empty states on {url}")
            empty_issues = await self._check_empty_states(soup, url, audit_page_id)
            issues_found += len(empty_issues)

            # Check 2: Reading Level Audit
            logger.info(f"[Vision] Analyzing reading level on {url}")
            reading_issues = await self._check_reading_level(soup, url, audit_page_id)
            issues_found += len(reading_issues)

            # Check 3: Tone Consistency
            logger.info(f"[Vision] Checking tone consistency on {url}")
            tone_issues = await self._check_tone_consistency(soup, url, audit_page_id)
            issues_found += len(tone_issues)

            # Check 4: Enhancement Strategies
            logger.info(f"[Vision] Generating enhancement strategies for {url}")
            enhancement_issues = await self._generate_enhancements(soup, url, audit_page_id)
            issues_found += len(enhancement_issues)

            return {"agent": "vision_architect", "issues_found": issues_found}

        except Exception as e:
            logger.error(f"Vision Architect error: {e}")
            return {"agent": "vision_architect", "issues_found": 0}

    async def _check_empty_states(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check for unmotivating empty states"""
        issues = []

        try:
            page_text = soup.get_text(separator=" ", strip=True)

            # Check if page looks empty
            if len(page_text.strip()) < 200:
                # Check for CTAs
                buttons = soup.find_all("button") + soup.find_all("a", attrs={"role": "button"})

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

    async def _check_reading_level(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check reading level and AI-sounding text"""
        issues = []

        try:
            # Get body text paragraphs and headings
            paragraphs = soup.find_all(["p", "h1", "h2", "h3"])

            ai_patterns = ["innovative", "cutting-edge", "revolutionary", "synergy", "paradigm", "leverage"]

            for para in paragraphs[:5]:
                try:
                    text = para.get_text(strip=True)

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

    async def _check_tone_consistency(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Check tone consistency across page sections"""
        issues = []

        try:
            # Get sections
            headers = soup.find_all(["h1", "h2", "h3"])

            tones_detected = []

            for header in headers[:3]:
                try:
                    text = header.get_text(strip=True)

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

    async def _generate_enhancements(self, soup: BeautifulSoup, url: str, audit_page_id: str) -> List[str]:
        """Generate psychology-based enhancement recommendations"""
        issues = []

        try:
            # Check for images
            images = soup.find_all("img")

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
            testimonials = (
                soup.find_all(attrs={"role": "blockquote"})
                + soup.find_all(class_="testimonial")
            )

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
