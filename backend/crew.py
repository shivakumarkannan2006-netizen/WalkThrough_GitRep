"""
Crew Orchestrator — Walk-Through Crew: 6 Agents + 3 Monitors

Architecture: Code-First, LLM-as-Judge.
Each page produces exactly 2 Gemini calls:
  - Call A: batched vision analysis (desktop + mobile + interaction screenshots)
  - Call B: text-only compliance + copy analysis

All agents receive the pre-collected PageBundle. No agent touches a browser.
All agents run via asyncio.gather() in parallel.
"""

import asyncio
import base64
import io
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
import textstat
from PIL import Image

import google.generativeai as genai

from config import get_settings
from navigator import PageBundle

logger = logging.getLogger(__name__)

LLM_SYSTEM_AGENT = "system"

# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------

def _build_image_part(b64_str: str) -> Dict:
    """Wrap base64 string as Gemini MIME part."""
    return {"mime_type": "image/jpeg", "data": b64_str}


def _init_gemini(api_key: str, model_name: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def _validate_call_a(data: Dict) -> bool:
    if not isinstance(data, dict):
        return False
    return all(k in data for k in CALL_A_SCHEMA["required"])


def _validate_call_b(data: Dict) -> bool:
    if not isinstance(data, dict):
        return False
    return all(k in data for k in CALL_B_SCHEMA["required"])


def _parse_json_response(text: str) -> Dict:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


def _usage_from_response(response) -> int:
    try:
        um = response.usage_metadata
        if um:
            return int((um.prompt_token_count or 0) + (um.candidates_token_count or 0))
    except Exception:
        pass
    return 0


async def _generate_json_with_retry(
    model,
    content,
    *,
    required_keys: List[str],
    validator,
    settings,
) -> Tuple[Dict, int, int]:
    """Call Gemini with retries; returns (parsed_dict, tokens_used, latency_ms)."""
    max_tokens = settings.gemini_max_output_tokens()
    last_error = None
    for attempt in range(settings.GEMINI_MAX_RETRIES):
        t0 = time.time()
        try:
            response = await asyncio.to_thread(
                model.generate_content,
                content,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    max_output_tokens=max_tokens,
                ),
            )
            latency_ms = int((time.time() - t0) * 1000)
            tokens = _usage_from_response(response)
            if not response.text:
                raise ValueError("Empty Gemini response text")
            parsed = _parse_json_response(response.text)
            if validator(parsed):
                return parsed, tokens, latency_ms
            last_error = ValueError("JSON missing required keys")
            content = (
                content
                if isinstance(content, str)
                else list(content)
            )
            if isinstance(content, list):
                content = content + [
                    "\n\nYour previous response was invalid. Return ONLY valid JSON matching the schema."
                ]
            else:
                content = content + "\n\nReturn ONLY valid JSON matching the schema."
        except Exception as e:
            last_error = e
            logger.warning(f"Gemini attempt {attempt + 1} failed: {e}")
            if attempt < settings.GEMINI_MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
    logger.error(f"Gemini failed after retries: {last_error}")
    return {}, 0, 0


def _interaction_ambiguous(bundle: PageBundle) -> bool:
    """True when programmatic checks need vision corroboration."""
    for timing in bundle.click_interaction_timings:
        if timing.get("response_ms", 0) > 500 and not timing.get("had_spinner"):
            return True
    for form in bundle.form_interaction_results:
        post = form.get("post_html", "")
        pre_len = form.get("pre_html_len", 0)
        if abs(len(post) - pre_len) > 200 and form.get("input_type") in ("empty", "spacebar"):
            return True
    return False


# ---------------------------------------------------------------------------
# Call A — Vision (desktop + mobile + optional interaction screenshots)
# ---------------------------------------------------------------------------

CALL_A_SCHEMA = {
    "type": "object",
    "properties": {
        "contrast_issues": {"type": "array", "items": {"type": "string"}},
        "layout_overlaps": {"type": "array", "items": {"type": "string"}},
        "placeholder_text": {"type": "array", "items": {"type": "string"}},
        "dark_patterns": {"type": "array", "items": {"type": "string"}},
        "mobile_keyboard_collision": {
            "type": "object",
            "properties": {
                "detected": {"type": "boolean"},
                "description": {"type": "string"},
            },
        },
        "horizontal_overflow_visual": {
            "type": "object",
            "properties": {
                "detected": {"type": "boolean"},
                "description": {"type": "string"},
            },
        },
        "general_polish_issues": {"type": "array", "items": {"type": "string"}},
        "empty_state": {
            "type": "object",
            "properties": {
                "detected": {"type": "boolean"},
                "description": {"type": "string"},
            },
        },
        "tone_sections": {
            "type": "object",
            "properties": {
                "hero_tone": {"type": "string"},
                "body_tone": {"type": "string"},
                "footer_tone": {"type": "string"},
            },
        },
        "psychology_enhancements": {"type": "array", "items": {"type": "string"}},
        "password_field_visible": {
            "type": "object",
            "properties": {
                "detected": {"type": "boolean"},
                "description": {"type": "string"},
            },
        },
        "back_button_result_issue": {
            "type": "object",
            "properties": {
                "detected": {"type": "boolean"},
                "description": {"type": "string"},
            },
        },
        "rage_click_result_issue": {
            "type": "object",
            "properties": {
                "detected": {"type": "boolean"},
                "description": {"type": "string"},
            },
        },
        "fout_detected": {
            "type": "object",
            "properties": {
                "detected": {"type": "boolean"},
                "description": {"type": "string"},
            },
        },
    },
    "required": [
        "contrast_issues", "layout_overlaps", "placeholder_text", "dark_patterns",
        "mobile_keyboard_collision", "horizontal_overflow_visual", "general_polish_issues",
        "empty_state", "tone_sections", "psychology_enhancements",
        "password_field_visible", "back_button_result_issue", "rage_click_result_issue",
        "fout_detected",
    ],
}


async def _call_a_vision(model, bundle: PageBundle, settings) -> Tuple[Dict, int, int]:
    """Batched vision call: desktop + mobile + interaction screenshots."""
    settings = settings or get_settings()
    if not settings.ENABLE_SCREENSHOTS:
        return {}, 0, 0
    if not bundle.screenshot_desktop_b64 and not bundle.screenshot_mobile_b64:
        return {}, 0, 0

    try:
        images = []
        notes = ["You are a team of senior web audit experts. Analyze the provided screenshots.\n"]

        if bundle.screenshot_desktop_b64:
            images.append(_build_image_part(bundle.screenshot_desktop_b64))
            notes.append(f"Image {len(images)}: Desktop screenshot (1280px)\n")
        if bundle.screenshot_mobile_b64:
            images.append(_build_image_part(bundle.screenshot_mobile_b64))
            notes.append(f"Image {len(images)}: Mobile screenshot (375px)\n")
        if bundle.screenshot_fout_b64:
            images.append(_build_image_part(bundle.screenshot_fout_b64))
            notes.append(f"Image {len(images)}: FOUT screenshot (before fonts loaded)\n")
        if bundle.back_button_result.get("triggered") and bundle.back_button_result.get("screenshot_b64"):
            images.append(_build_image_part(bundle.back_button_result["screenshot_b64"]))
            notes.append(f"Image {len(images)}: Back-button result screenshot\n")
        if bundle.persona_frustrated_screenshot_b64:
            images.append(_build_image_part(bundle.persona_frustrated_screenshot_b64))
            notes.append(f"Image {len(images)}: After rage-click simulation\n")
        if bundle.password_field_screenshots:
            images.append(_build_image_part(bundle.password_field_screenshots[0]["screenshot_b64"]))
            notes.append(f"Image {len(images)}: Password field with test value\n")

        if _interaction_ambiguous(bundle):
            for timing in bundle.click_interaction_timings:
                snap = timing.get("snapshot_b64")
                if snap:
                    images.append(_build_image_part(snap))
                    notes.append(
                        f"Image {len(images)}: After clicking '{timing.get('selector', 'button')}'\n"
                    )
                    break
            for form in bundle.form_interaction_results:
                snap = form.get("post_screenshot_b64")
                if snap:
                    images.append(_build_image_part(snap))
                    notes.append(
                        f"Image {len(images)}: After form submit ({form.get('input_type', 'test')})\n"
                    )
                    break

        prompt = (
            "".join(notes)
            + "\nReturn JSON with keys: "
            + ", ".join(CALL_A_SCHEMA["required"])
            + ".\n"
            "contrast_issues, layout_overlaps, placeholder_text, dark_patterns, "
            "mobile_keyboard_collision, horizontal_overflow_visual, general_polish_issues, "
            "empty_state, tone_sections, psychology_enhancements, password_field_visible, "
            "back_button_result_issue, rage_click_result_issue, fout_detected."
        )
        content = [prompt] + images
        return await _generate_json_with_retry(
            model,
            content,
            required_keys=CALL_A_SCHEMA["required"],
            validator=_validate_call_a,
            settings=settings,
        )
    except Exception as e:
        logger.error(f"Call A vision error for {bundle.url}: {e}")
        return {}, 0, 0


# ---------------------------------------------------------------------------
# Call B — Text-only compliance + copy analysis
# ---------------------------------------------------------------------------

CALL_B_SCHEMA = {
    "type": "object",
    "properties": {
        "gdpr_issues": {"type": "array", "items": {"type": "string"}},
        "ai_act_issues": {"type": "array", "items": {"type": "string"}},
        "ai_generated_copy_score": {"type": "integer"},
        "ai_generated_copy_explanation": {"type": "string"},
        "reading_level_grade": {"type": "number"},
        "testimonial_authenticity": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text_snippet": {"type": "string"},
                    "ai_score": {"type": "integer"},
                    "reason": {"type": "string"},
                },
            },
        },
        "pricing_claims": {"type": "array", "items": {"type": "string"}},
        "contact_info": {"type": "array", "items": {"type": "string"}},
        "console_sensitive_data": {"type": "array", "items": {"type": "string"}},
        "pdf_contradictions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "gdpr_issues", "ai_act_issues", "ai_generated_copy_score",
        "ai_generated_copy_explanation", "reading_level_grade",
        "testimonial_authenticity", "pricing_claims", "contact_info",
        "console_sensitive_data", "pdf_contradictions",
    ],
}


async def _call_b_text(
    model, bundle: PageBundle, pdf_rag_chunks: List[str] = None, settings=None
) -> Tuple[Dict, int, int]:
    """Text-only compliance, copy quality, and GDPR analysis."""
    settings = settings or get_settings()
    try:
        text_content = "\n".join(bundle.page_text_blocks[:100])
        testimonials_text = (
            "\n---\n".join(bundle.testimonial_blocks[:10])
            if bundle.testimonial_blocks
            else "None found"
        )
        ambiguous_logs = [
            e["text"]
            for e in bundle.console_logs
            if len(e.get("text", "")) > 20 and e.get("type") in ("error", "warning", "log")
        ][:20]
        console_text = "\n".join(ambiguous_logs) if ambiguous_logs else "None"
        pdf_section = ""
        if pdf_rag_chunks:
            pdf_section = (
                "\n\nCOMPANY POLICY DOCUMENTS:\n" + "\n---\n".join(pdf_rag_chunks[:5])
            )

        prompt = (
            f"You are a legal compliance expert, senior copywriter, and UX auditor.\n\n"
            f"PAGE URL: {bundle.url}\n\n"
            f"PAGE TEXT:\n{text_content}\n\n"
            f"TESTIMONIALS:\n{testimonials_text}\n\n"
            f"BROWSER CONSOLE LOGS:\n{console_text}\n\n"
            f"PRICES: {', '.join(bundle.prices_found) if bundle.prices_found else 'None'}\n"
            f"CONTACT: {', '.join(bundle.contact_info_found) if bundle.contact_info_found else 'None'}\n"
            + pdf_section
            + "\n\nReturn JSON with keys: "
            + ", ".join(CALL_B_SCHEMA["required"])
        )
        return await _generate_json_with_retry(
            model,
            prompt,
            required_keys=CALL_B_SCHEMA["required"],
            validator=_validate_call_b,
            settings=settings,
        )
    except Exception as e:
        logger.error(f"Call B text error for {bundle.url}: {e}")
        return {}, 0, 0


# ---------------------------------------------------------------------------
# Crew Orchestrator
# ---------------------------------------------------------------------------

class CrewOrchestrator:
    """Orchestrates all 6 agents + 3 monitors in parallel on each PageBundle."""

    def __init__(self, supabase_client, audit_session_id: str, broadcast_fn=None):
        self.supabase = supabase_client
        self.audit_session_id = audit_session_id
        self.broadcast = broadcast_fn or (lambda x: None)
        self.settings = get_settings()

        self._all_prices: List[Dict] = []
        self._all_contacts: List[Dict] = []
        self._page_metas: List[Dict] = []
        self._gemini_calls_made = 0
        self._llm_budget_exhausted = False

        self._model = None
        if self.settings.ENABLE_LLM_ANALYSIS:
            if not self.settings.GEMINI_API_KEY:
                logger.error("ENABLE_LLM_ANALYSIS is true but GEMINI_API_KEY is missing")
            else:
                try:
                    self._model = _init_gemini(
                        self.settings.GEMINI_API_KEY, self.settings.GEMINI_MODEL
                    )
                except Exception as e:
                    logger.error(f"Gemini init error: {e}")

    def _gemini_budget_remaining(self) -> bool:
        cap = self.settings.MAX_GEMINI_CALLS_PER_AUDIT
        if cap <= 0:
            return True
        return self._gemini_calls_made < cap

    def _should_run_call_a(self, bundle: PageBundle) -> bool:
        if not self.settings.ENABLE_LLM_ANALYSIS or self.settings.is_quick_profile():
            return False
        if not self._model or self._llm_budget_exhausted:
            return False
        if not self.settings.ENABLE_SCREENSHOTS:
            return False
        if not bundle.screenshot_desktop_b64 and not bundle.screenshot_mobile_b64:
            return False
        return self._gemini_budget_remaining()

    def _should_run_call_b(self, bundle: PageBundle) -> bool:
        if not self.settings.ENABLE_LLM_ANALYSIS or self.settings.is_quick_profile():
            return False
        if not self._model or self._llm_budget_exhausted:
            return False
        thin = len(bundle.page_text_blocks) < 5
        has_signals = bool(
            bundle.testimonial_blocks or bundle.prices_found or bundle.contact_info_found
        )
        if thin and not has_signals:
            return False
        return self._gemini_budget_remaining()

    def _record_llm_unavailable(
        self, url: str, audit_page_id: str, call_name: str, reason: str
    ) -> None:
        self._save_issue(
            LLM_SYSTEM_AGENT,
            "LLM Analysis Unavailable",
            f"{call_name} skipped for {url}: {reason}",
            "medium",
            url,
            audit_page_id,
            "Verify GEMINI_API_KEY, quotas, and ENABLE_LLM_ANALYSIS settings.",
        )

    async def analyze_page(self, bundle: PageBundle):
        """Run all agents + monitors in parallel on a pre-collected PageBundle."""
        if not self.supabase:
            logger.error("analyze_page called with no Supabase client")
            return

        try:
            url = bundle.url
            pid = bundle.audit_page_id
            logger.info(f"Crew analyzing: {url}")

            self._page_metas.append({
                "url": url,
                "title": bundle.page_title,
                "meta_description": getattr(bundle, "meta_description", "") or "",
            })

            pdf_chunks = await self._fetch_rag_chunks(bundle)

            run_a = self._should_run_call_a(bundle)
            run_b = self._should_run_call_b(bundle)

            if self.settings.ENABLE_LLM_ANALYSIS and not self.settings.is_quick_profile():
                if not self._model:
                    self._record_llm_unavailable(
                        url, pid, "Vision and text analysis",
                        "Gemini model not initialized (missing or invalid API key)",
                    )
                elif self._llm_budget_exhausted:
                    self._record_llm_unavailable(
                        url, pid, "Vision and text analysis",
                        f"Gemini call budget exhausted ({self.settings.MAX_GEMINI_CALLS_PER_AUDIT} calls)",
                    )

            call_a_result: Dict = {}
            call_b_result: Dict = {}
            metrics: List[Dict] = []

            async def _run_a():
                if not run_a:
                    return {}, 0, 0
                return await _call_a_vision(self._model, bundle, self.settings)

            async def _run_b():
                if not run_b:
                    return {}, 0, 0
                return await _call_b_text(
                    self._model, bundle, pdf_chunks, self.settings
                )

            raw_a, raw_b = await asyncio.gather(_run_a(), _run_b(), return_exceptions=True)

            if isinstance(raw_a, Exception):
                logger.error(f"Call A failed for {url}: {raw_a}")
                call_a_result, tok_a, lat_a = {}, 0, 0
            else:
                call_a_result, tok_a, lat_a = raw_a
                if run_a:
                    self._gemini_calls_made += 1
                    metrics.append({
                        "agent_name": "call_a_vision",
                        "tokens": tok_a,
                        "latency_ms": lat_a,
                        "response": call_a_result,
                    })

            if isinstance(raw_b, Exception):
                logger.error(f"Call B failed for {url}: {raw_b}")
                call_b_result, tok_b, lat_b = {}, 0, 0
            else:
                call_b_result, tok_b, lat_b = raw_b
                if run_b:
                    self._gemini_calls_made += 1
                    metrics.append({
                        "agent_name": "call_b_text",
                        "tokens": tok_b,
                        "latency_ms": lat_b,
                        "response": call_b_result,
                    })

            cap = self.settings.MAX_GEMINI_CALLS_PER_AUDIT
            if cap > 0 and self._gemini_calls_made >= cap:
                self._llm_budget_exhausted = True

            if run_a and not call_a_result:
                self._record_llm_unavailable(
                    url, pid, "Vision analysis (Call A)",
                    "Gemini returned empty or invalid JSON after retries",
                )
            if run_b and not call_b_result:
                self._record_llm_unavailable(
                    url, pid, "Text compliance analysis (Call B)",
                    "Gemini returned empty or invalid JSON after retries",
                )

            await self._log_llm_interactions(url, metrics)

            # Collect cross-page data
            if bundle.prices_found:
                self._all_prices.append({"url": url, "prices": bundle.prices_found})
            if bundle.contact_info_found:
                self._all_contacts.append({"url": url, "contacts": bundle.contact_info_found})

            # Instantiate all agents
            agents = [
                GhostNavigator(self.supabase, self.audit_session_id),
                MirrorStylist(self.supabase, self.audit_session_id),
                VaultCounsel(self.supabase, self.audit_session_id),
                FactChecker(self.supabase, self.audit_session_id),
                FortressSentry(self.supabase, self.audit_session_id),
                VisionArchitect(self.supabase, self.audit_session_id),
                InternalStateMonitor(self.supabase, self.audit_session_id),
            ]

            # Run all agents in parallel — no browser access, pure data analysis
            results = await asyncio.gather(
                *[agent.analyze(bundle, call_a_result, call_b_result) for agent in agents],
                return_exceptions=True,
            )

            issues_count = sum(
                r.get("issues_found", 0) for r in results if isinstance(r, dict)
            )
            for i, r in enumerate(results):
                if isinstance(r, Exception):
                    logger.error(f"Agent {i} error for {url}: {r}")

            await self.broadcast({
                "type": "page_analyzed",
                "url": url,
                "issues_found": issues_count,
            })

        except Exception as e:
            logger.error(f"Crew orchestration error for {bundle.url}: {e}")

    async def run_post_traversal_pass(self):
        """Cross-page consistency checks after all pages are analyzed."""
        try:
            await self._check_pricing_consistency()
            await self._check_contact_ghosting()
            await self._check_duplicate_meta_titles()
        except Exception as e:
            logger.error(f"Post-traversal pass error: {e}")

    async def _check_duplicate_meta_titles(self):
        """Flag duplicate page titles or meta descriptions across the audit."""
        if len(self._page_metas) < 2:
            return
        title_map: Dict[str, List[str]] = {}
        meta_map: Dict[str, List[str]] = {}
        for entry in self._page_metas:
            title = (entry.get("title") or "").strip()
            meta = (entry.get("meta_description") or "").strip()
            if title:
                title_map.setdefault(title, []).append(entry["url"])
            if meta and len(meta) > 20:
                meta_map.setdefault(meta, []).append(entry["url"])

        for title, urls in title_map.items():
            if len(urls) > 1:
                self._save_issue(
                    LLM_SYSTEM_AGENT,
                    "Duplicate Page Title",
                    f"Same title '{title[:80]}' on {len(urls)} pages: {', '.join(urls[:5])}",
                    "medium",
                    urls[0],
                    "",
                    "Use unique, descriptive titles per page for SEO and accessibility.",
                )

        for meta, urls in meta_map.items():
            if len(urls) > 1:
                self._save_issue(
                    LLM_SYSTEM_AGENT,
                    "Duplicate Meta Description",
                    f"Same meta description on {len(urls)} pages: {', '.join(urls[:5])}",
                    "low",
                    urls[0],
                    "",
                    "Write unique meta descriptions for each page.",
                )

    async def _fetch_rag_chunks(self, bundle: PageBundle) -> List[str]:
        """Fetch top-5 relevant PDF chunks for this page via cosine similarity."""
        if not self.settings.ENABLE_RAG_VAULT_COUNSEL:
            return []
        try:
            resp = self.supabase.table("company_document_embeddings").select(
                "chunk_text"
            ).limit(5).execute()
            if resp.data:
                return [row["chunk_text"] for row in resp.data]
        except Exception as e:
            logger.debug(f"RAG fetch error: {e}")
        return []

    async def _log_llm_interactions(self, url: str, metrics: List[Dict]):
        if not metrics:
            return
        try:
            now = datetime.now(timezone.utc).isoformat()
            rows = []
            for m in metrics:
                rows.append({
                    "audit_session_id": self.audit_session_id,
                    "agent_name": m["agent_name"],
                    "prompt_text": f"{m['agent_name']} for {url}",
                    "llm_model_used": self.settings.GEMINI_MODEL,
                    "response_text": str(m.get("response", {}))[:2000],
                    "tokens_used": m.get("tokens", 0),
                    "response_latency_ms": m.get("latency_ms", 0),
                    "timestamp": now,
                })
            self.supabase.table("llm_interactions").insert(rows).execute()
        except Exception as e:
            logger.debug(f"LLM interaction log error: {e}")

    def _save_issue(self, agent_name: str, category: str, detail: str, severity: str,
                    url: str, audit_page_id: str, remediation: str = "", extra: Dict = None):
        try:
            row = {
                "audit_session_id": self.audit_session_id,
                "agent_name": agent_name,
                "issue_category": category,
                "specific_issue_detail": detail,
                "severity": severity,
                "affected_url": url,
                "remediation_suggestion": remediation,
                "additional_data": extra or {},
            }
            self.supabase.table("audit_issues").insert(row).execute()
        except Exception as e:
            logger.error(f"save_issue error: {e}")

    async def _check_pricing_consistency(self):
        """Cross-page pricing comparison — flag same product, different price."""
        try:
            if len(self._all_prices) < 2:
                return
            # Build a flat set of all prices seen across all pages
            all_price_values = {}
            for entry in self._all_prices:
                for price in entry["prices"]:
                    # Normalize: strip currency symbols
                    numeric = re.sub(r"[^\d.]", "", price)
                    if numeric not in all_price_values:
                        all_price_values[numeric] = []
                    all_price_values[numeric].append(entry["url"])

            # Find prices that appear on some pages but not others (inconsistency signal)
            # More practically: find price values that are duplicated but differ
            # We flag if the same page has wildly different prices vs other pages
            # Simple heuristic: if price set on one page differs from another, report
            price_sets = [(e["url"], set(re.sub(r"[^\d.]", "", p) for p in e["prices"]))
                          for e in self._all_prices]
            for i, (url_a, prices_a) in enumerate(price_sets):
                for url_b, prices_b in price_sets[i+1:]:
                    if prices_a and prices_b and prices_a != prices_b:
                        symmetric_diff = prices_a.symmetric_difference(prices_b)
                        if symmetric_diff:
                            try:
                                self.supabase.table("pricing_inconsistencies").insert({
                                    "audit_session_id": self.audit_session_id,
                                    "location_1_url": url_a,
                                    "location_1_price": ", ".join(prices_a),
                                    "location_2_url": url_b,
                                    "location_2_price": ", ".join(prices_b),
                                    "currency": "mixed",
                                }).execute()
                            except Exception:
                                pass
                            self._save_issue(
                                "vault_counsel", "Pricing Consistency",
                                f"Price mismatch between {url_a} and {url_b}: {symmetric_diff}",
                                "high", url_a, "", "Verify all price references are consistent across all pages."
                            )
                            break
        except Exception as e:
            logger.error(f"Pricing consistency check error: {e}")

    async def _check_contact_ghosting(self):
        """Cross-page contact info comparison — flag mismatches."""
        try:
            if len(self._all_contacts) < 2:
                return
            reference_url = self._all_contacts[0]["url"]
            reference_contacts = set(self._all_contacts[0]["contacts"])
            for entry in self._all_contacts[1:]:
                page_contacts = set(entry["contacts"])
                if reference_contacts and page_contacts:
                    mismatches = reference_contacts.symmetric_difference(page_contacts)
                    if mismatches:
                        try:
                            self.supabase.table("contact_info_mismatches").insert({
                                "audit_session_id": self.audit_session_id,
                                "page_1_url": reference_url,
                                "page_1_email": ", ".join(c for c in reference_contacts if "@" in c),
                                "page_2_url": entry["url"],
                                "page_2_email": ", ".join(c for c in page_contacts if "@" in c),
                                "mismatch_type": "contact_info_ghosting",
                            }).execute()
                        except Exception:
                            pass
                        self._save_issue(
                            "vault_counsel", "Contact Info Ghosting",
                            f"Contact info differs between {reference_url} and {entry['url']}: {mismatches}",
                            "medium", entry["url"], "",
                            "Ensure support emails/phones are consistent across footer, contact page, and policies."
                        )
        except Exception as e:
            logger.error(f"Contact ghosting check error: {e}")


# ---------------------------------------------------------------------------
# Base Agent
# ---------------------------------------------------------------------------

class BaseAgent:
    def __init__(self, supabase, audit_session_id: str):
        self.supabase = supabase
        self.audit_session_id = audit_session_id
        self.settings = get_settings()

    def _save_issue(self, agent_name: str, category: str, detail: str, severity: str,
                    url: str, audit_page_id: str, remediation: str = "", extra: Dict = None) -> int:
        try:
            row = {
                "audit_session_id": self.audit_session_id,
                "agent_name": agent_name,
                "issue_category": category,
                "specific_issue_detail": detail,
                "severity": severity,
                "affected_url": url,
                "remediation_suggestion": remediation,
                "additional_data": extra or {},
            }
            self.supabase.table("audit_issues").insert(row).execute()
            return 1
        except Exception as e:
            logger.error(f"{agent_name} save_issue error: {e}")
            return 0

    async def analyze(self, bundle: PageBundle, call_a: Dict, call_b: Dict) -> Dict:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Agent 1: Ghost Navigator — Logic & Reliability
# ---------------------------------------------------------------------------

class GhostNavigator(BaseAgent):
    AGENT = "ghost_navigator"

    async def analyze(self, bundle: PageBundle, call_a: Dict, call_b: Dict) -> Dict:
        issues_found = 0
        url = bundle.url
        pid = bundle.audit_page_id

        # 1. 404s / Broken Routes
        if bundle.http_status_code >= 400:
            issues_found += self._save_issue(
                self.AGENT, "Fake Navigator / Broken Route",
                f"Page returned HTTP {bundle.http_status_code}: {url}",
                "critical", url, pid,
                "Fix the route or return a proper redirect. Remove dead links from navigation.",
            )
        elif bundle.page_text_blocks:
            full_text = " ".join(bundle.page_text_blocks).lower()
            error_phrases = ["404", "page not found", "not found", "doesn't exist", "does not exist",
                             "page unavailable", "error 404"]
            if any(p in full_text for p in error_phrases):
                issues_found += self._save_issue(
                    self.AGENT, "Fake Navigator / Broken Route",
                    f"Page content suggests a 404/error state despite HTTP 200: {url}",
                    "high", url, pid,
                    "Ensure error pages return proper 4xx status codes.",
                )

        # 2. Long loading times (>5s even before baseline comparison)
        if bundle.load_time_ms > 5000:
            issues_found += self._save_issue(
                self.AGENT, "Loading State Fatigue",
                f"Page took {bundle.load_time_ms}ms to load (>{5000}ms threshold): {url}",
                "high", url, pid,
                "Investigate server response time, large resources, or render-blocking scripts.",
            )

        # 3. Form Loopholes — compare pre/post HTML for error elements
        for result in bundle.form_interaction_results:
            post_html = result.get("post_html", "")
            pre_len = result.get("pre_html_len", 0)
            input_type = result.get("input_type", "")
            form_sel = result.get("form_selector", "")

            # Check: did any error message DOM element appear after submission?
            error_appeared = bool(re.search(
                r'(error|invalid|required|please|must|cannot|blank)',
                post_html.lower()[pre_len:pre_len + 5000] if len(post_html) > pre_len else post_html.lower()
            ))
            # Check: did the page grow significantly (success page loaded)?
            page_changed = abs(len(post_html) - pre_len) > 200

            if not error_appeared and page_changed and input_type in ("empty", "spacebar"):
                issues_found += self._save_issue(
                    self.AGENT, "Form Loop-Holes",
                    f"Form '{form_sel}' accepted {input_type} input without showing an error message.",
                    "high", url, pid,
                    "Add server-side and client-side validation. Reject blank/whitespace-only submissions.",
                    {"input_type": input_type, "form_selector": form_sel},
                )

            if not error_appeared and page_changed and input_type == "fake_email":
                issues_found += self._save_issue(
                    self.AGENT, "Form Loop-Holes",
                    f"Form '{form_sel}' accepted a fake email domain (fakefakedomain99.xyz) without validation.",
                    "medium", url, pid,
                    "Add email domain validation or MX record verification.",
                    {"input_type": input_type, "form_selector": form_sel},
                )

        # 4. Back Button Paradox — from Call A
        back_issue = call_a.get("back_button_result_issue", {})
        if back_issue.get("detected"):
            issues_found += self._save_issue(
                self.AGENT, "Back Button Paradox",
                f"Back button causes login wall or expired state: {back_issue.get('description', '')}",
                "high", url, pid,
                "Implement proper session state management. Avoid using POST-only flows without PRG pattern.",
            )
        # Also check programmatically
        if bundle.back_button_result.get("triggered"):
            result_url = bundle.back_button_result.get("result_url", "")
            login_indicators = ["login", "signin", "sign-in", "auth", "expired"]
            if any(ind in result_url.lower() for ind in login_indicators):
                issues_found += self._save_issue(
                    self.AGENT, "Back Button Paradox",
                    f"Back navigation redirected to login page: {result_url}",
                    "high", url, pid,
                    "Implement session restoration or retain authenticated state on back navigation.",
                )

        # 5. Deep Link Accuracy — anchor scroll tests
        for result in bundle.anchor_click_results:
            href = result.get("href", "")
            scroll_before = result.get("scroll_y_before", 0)
            scroll_after = result.get("scroll_y_after", 0)
            in_viewport = result.get("target_in_viewport", True)

            # If scroll didn't change AND we're still at top, anchor is broken
            if scroll_after == 0 and scroll_before == 0 and not in_viewport and href != "#":
                issues_found += self._save_issue(
                    self.AGENT, "Deep Link Accuracy",
                    f"Anchor link '{href}' did not scroll to target element.",
                    "medium", url, pid,
                    f"Ensure an element with id='{href.lstrip('#')}' exists and is not hidden.",
                    {"href": href},
                )

        # 6. Orphaned States — success/confirmation pages with no CTA
        full_text = " ".join(bundle.page_text_blocks).lower()
        success_indicators = ["order confirmed", "successfully submitted", "thank you for", "payment successful",
                               "subscription activated", "registration complete"]
        is_success_page = any(ind in full_text for ind in success_indicators)
        if is_success_page:
            has_cta = any(
                el.get("width", 0) > 0
                for el in bundle.interactive_element_bounding_boxes
                if "button" in el.get("selector", "").lower() or "a#" in el.get("selector", "").lower()
            )
            if not has_cta:
                issues_found += self._save_issue(
                    self.AGENT, "Orphaned States",
                    f"Success/confirmation page '{url}' has no visible CTA to return home or proceed.",
                    "medium", url, pid,
                    "Add a clear 'Return to Home' or 'View Your Order' button on confirmation pages.",
                )

        # 7. Loading State Fatigue — buttons with >300ms response, no spinner
        for timing in bundle.click_interaction_timings:
            if timing.get("response_ms", 0) > self.settings.LOADING_STATE_THRESHOLD_MS:
                issues_found += self._save_issue(
                    self.AGENT, "Loading State Fatigue",
                    f"Button '{timing.get('selector', '')}' took {timing.get('response_ms')}ms with no loading indicator.",
                    "medium", url, pid,
                    "Add a spinner or disabled state immediately on click to prevent rage-clicking.",
                    {"selector": timing.get("selector"), "response_ms": timing.get("response_ms")},
                )

        return {"issues_found": issues_found}


# ---------------------------------------------------------------------------
# Agent 2: Mirror Stylist — Aesthetics & UX
# ---------------------------------------------------------------------------

class MirrorStylist(BaseAgent):
    AGENT = "mirror_stylist"

    async def analyze(self, bundle: PageBundle, call_a: Dict, call_b: Dict) -> Dict:
        issues_found = 0
        url = bundle.url
        pid = bundle.audit_page_id

        # 1. Contrast failures — from AXE tree (programmatic, free)
        contrast_issues_axe = self._extract_axe_contrast(bundle.axe_tree)
        for issue in contrast_issues_axe:
            self._save_issue(
                self.AGENT, "Visual Contrast Failure",
                f"AXE accessibility: {issue}",
                "high", url, pid,
                "Ensure text meets WCAG AA contrast ratio of at least 4.5:1 for normal text.",
            )
            issues_found += 1

        # Also from Call A
        for item in call_a.get("contrast_issues", []):
            issues_found += self._save_issue(
                self.AGENT, "Visual Contrast Failure",
                item, "high", url, pid,
                "Increase contrast between text and background colours.",
            )

        # 2. Z-Index Collisions
        for item in call_a.get("layout_overlaps", []):
            issues_found += self._save_issue(
                self.AGENT, "Z-Index Collision",
                item, "medium", url, pid,
                "Review z-index stacking context for sticky headers, modals, and notification banners.",
            )
            try:
                self.supabase.table("z_index_collisions").insert({
                    "audit_page_id": pid,
                    "element_1_selector": "unknown",
                    "element_2_selector": "unknown",
                    "collision_description": item,
                }).execute()
            except Exception:
                pass

        # 3. Touch Target Density — visible interactive elements under 44x44px
        for el in bundle.interactive_element_bounding_boxes:
            w = el.get("width", 100)
            h = el.get("height", 100)
            sel = el.get("selector", "")
            if w > 0 and h > 0 and (w < 44 or h < 44):
                issues_found += self._save_issue(
                    self.AGENT, "Touch-Target Density",
                    f"Interactive element '{sel}' is {w}x{h}px — below 44x44px minimum for touch targets.",
                    "medium", url, pid,
                    "Increase button/link size to at least 44x44px for mobile usability.",
                    {"selector": sel, "width": w, "height": h},
                )
                try:
                    self.supabase.table("touch_target_failures").insert({
                        "audit_page_id": pid,
                        "element_selector": sel,
                        "width_px": int(w),
                        "height_px": int(h),
                        "failure_type": "undersized_touch_target",
                    }).execute()
                except Exception:
                    pass

        # Check spacing between elements (centroids within 8px)
        elements = [(el.get("x", 0) + el.get("width", 0)/2,
                     el.get("y", 0) + el.get("height", 0)/2,
                     el.get("selector", "")) for el in bundle.interactive_element_bounding_boxes]
        for i, (cx1, cy1, sel1) in enumerate(elements):
            for cx2, cy2, sel2 in elements[i+1:]:
                dist = ((cx2 - cx1) ** 2 + (cy2 - cy1) ** 2) ** 0.5
                if 0 < dist < 8:
                    issues_found += self._save_issue(
                        self.AGENT, "Touch-Target Density",
                        f"Elements '{sel1}' and '{sel2}' are only {dist:.1f}px apart — too close for accurate tapping.",
                        "medium", url, pid,
                        "Add at least 8px spacing between interactive elements.",
                    )

        # 4. Horizontal Scroll Bug — programmatic check first
        if bundle.viewport_overflow.get("has_overflow"):
            issues_found += self._save_issue(
                self.AGENT, "Horizontal Scroll Bug",
                f"Page scrollWidth ({bundle.viewport_overflow.get('scroll_width')}px) exceeds viewport ({bundle.viewport_overflow.get('window_width')}px).",
                "medium", url, pid,
                "Find and constrain the overflowing element. Add overflow-x: hidden to body or fix the offending element.",
            )
        # Corroborate with vision
        h_overflow = call_a.get("horizontal_overflow_visual", {})
        if h_overflow.get("detected") and not bundle.viewport_overflow.get("has_overflow"):
            issues_found += self._save_issue(
                self.AGENT, "Horizontal Scroll Bug",
                f"Visual overflow detected by vision analysis: {h_overflow.get('description', '')}",
                "medium", url, pid,
                "Inspect elements near viewport edge for negative margins or absolute positioning.",
            )

        # 5. FOUT — Pillow diff already computed in navigator
        fout = call_a.get("fout_detected", {})
        if fout.get("detected"):
            issues_found += self._save_issue(
                self.AGENT, "Font Jump (FOUT)",
                f"Flash of unstyled text detected: {fout.get('description', '')}",
                "low", url, pid,
                "Use font-display: swap or preload web fonts to eliminate layout shift from font loading.",
            )

        # 6. Mobile Integrity / Keyboard Collision
        if bundle.mobile_layout_shift_detected:
            issues_found += self._save_issue(
                self.AGENT, "Mobile Integrity",
                "Significant layout difference detected between desktop and mobile viewports.",
                "medium", url, pid,
                "Test responsive breakpoints. Ensure no content is hidden or displaced on mobile.",
            )
        mob_kb = call_a.get("mobile_keyboard_collision", {})
        if mob_kb.get("detected"):
            issues_found += self._save_issue(
                self.AGENT, "Mobile Integrity",
                f"Mobile keyboard collision: {mob_kb.get('description', '')}",
                "medium", url, pid,
                "Use viewport meta with height adjustments to prevent keyboard from covering inputs.",
            )

        # 7. Placeholder text / Polish / Typos
        for item in call_a.get("placeholder_text", []):
            issues_found += self._save_issue(
                self.AGENT, "General Polish",
                f"Placeholder/lorem ipsum text found: {item}",
                "high", url, pid,
                "Replace all placeholder content with real copy before going live.",
            )
        for item in call_a.get("general_polish_issues", []):
            issues_found += self._save_issue(
                self.AGENT, "General Polish",
                item, "low", url, pid,
                "Review and fix visual inconsistency.",
            )

        # Store contrast failures in dedicated table
        for item in call_a.get("contrast_issues", []):
            try:
                self.supabase.table("contrast_failures").insert({
                    "audit_page_id": pid,
                    "element_selector": "vision-detected",
                    "wcag_level": "FAIL",
                    "element_text": item[:200],
                }).execute()
            except Exception:
                pass

        return {"issues_found": issues_found}

    def _extract_axe_contrast(self, axe_tree) -> List[str]:
        """Recursively extract contrast violations from Playwright accessibility tree."""
        issues = []
        if not axe_tree:
            return issues
        try:
            def _walk(node):
                if isinstance(node, dict):
                    role = node.get("role", "")
                    name = node.get("name", "")
                    if "contrast" in name.lower():
                        issues.append(f"Accessibility: {name}")
                    for child in node.get("children", []):
                        _walk(child)
            _walk(axe_tree)
        except Exception:
            pass
        return issues


# ---------------------------------------------------------------------------
# Agent 3: Vault Counsel — Compliance & Integrity
# ---------------------------------------------------------------------------

# Known tracking cookie name prefixes (pre-consent check)
_TRACKING_COOKIE_PATTERNS = [
    "_ga", "_gid", "_gat", "fbp", "_fbq", "__fbp", "_gcl", "fr", "__utma",
    "__utmb", "__utmc", "__utmz", "_hjid", "_hjincludedinsamplerate", "ajs_",
]

class VaultCounsel(BaseAgent):
    AGENT = "vault_counsel"

    async def analyze(self, bundle: PageBundle, call_a: Dict, call_b: Dict) -> Dict:
        issues_found = 0
        url = bundle.url
        pid = bundle.audit_page_id

        # 1. GDPR Issues (from Call B)
        for item in call_b.get("gdpr_issues", []):
            issues_found += self._save_issue(
                self.AGENT, "GDPR / AI Act",
                item, "high", url, pid,
                "Consult a data protection lawyer to remediate this GDPR violation.",
            )
            try:
                self.supabase.table("gdpr_issues").insert({
                    "audit_session_id": self.audit_session_id,
                    "issue_type": "gdpr",
                    "affected_page_url": url,
                    "relevant_text": item[:500],
                    "severity": "high",
                }).execute()
            except Exception:
                pass

        for item in call_b.get("ai_act_issues", []):
            issues_found += self._save_issue(
                self.AGENT, "GDPR / AI Act",
                f"EU AI Act: {item}", "high", url, pid,
                "Review EU AI Act Articles for compliance requirements.",
            )

        # 2. Cookie Banner Integrity — programmatic, zero LLM
        tracking_before_consent = [
            c["name"] for c in bundle.cookies_on_load
            if any(c["name"].lower().startswith(p) for p in _TRACKING_COOKIE_PATTERNS)
        ]
        if tracking_before_consent:
            issues_found += self._save_issue(
                self.AGENT, "Cookie Banner Integrity",
                f"Tracking cookies set before user consent: {tracking_before_consent}",
                "critical", url, pid,
                "Block all analytics/tracking cookies until user explicitly accepts the cookie banner.",
                {"cookies": tracking_before_consent},
            )
            for cookie_name in tracking_before_consent:
                try:
                    self.supabase.table("cookie_consent_violations").insert({
                        "audit_session_id": self.audit_session_id,
                        "cookie_name": cookie_name,
                        "set_before_consent": True,
                        "consent_type": "tracking",
                    }).execute()
                except Exception:
                    pass

        # 3. Dark Patterns (from Call A)
        for item in call_a.get("dark_patterns", []):
            issues_found += self._save_issue(
                self.AGENT, "Dark Pattern Detection",
                item, "high", url, pid,
                "Remove or redesign deceptive UI elements to comply with consumer protection regulations.",
            )

        # 4. PDF RAG contradictions (from Call B)
        for item in call_b.get("pdf_contradictions", []):
            issues_found += self._save_issue(
                self.AGENT, "Legal Vault",
                f"Site content contradicts company policy document: {item}",
                "critical", url, pid,
                "Review this claim against the uploaded legal/policy documents and amend as necessary.",
            )

        return {"issues_found": issues_found}


# ---------------------------------------------------------------------------
# Agent 4: Fact Checker — Citation Verification + Testimonials
# ---------------------------------------------------------------------------

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

class FactChecker(BaseAgent):
    AGENT = "fact_checker"

    async def analyze(self, bundle: PageBundle, call_a: Dict, call_b: Dict) -> Dict:
        issues_found = 0
        url = bundle.url
        pid = bundle.audit_page_id

        # 1. Citation Verifier — physically visit every external link
        if bundle.external_links:
            link_results = await self._verify_links(bundle.external_links)
            for result in link_results:
                link_url = result["url"]
                status = result["status"]
                reachable = result["reachable"]
                redirect_domain = result.get("redirect_domain")

                try:
                    self.supabase.table("audit_external_links").insert({
                        "audit_session_id": self.audit_session_id,
                        "link_url": link_url,
                        "http_status_code": status,
                        "response_time_ms": result.get("response_ms"),
                        "reachable": reachable,
                        "found_on_page": url,
                    }).execute()
                except Exception:
                    pass

                if not reachable or status >= 400:
                    issues_found += self._save_issue(
                        self.AGENT, "Citation Verifier",
                        f"Broken external link (HTTP {status}): {link_url}",
                        "high", url, pid,
                        "Remove or update this broken link.",
                        {"link_url": link_url, "http_status": status},
                    )
                elif redirect_domain and redirect_domain not in link_url:
                    issues_found += self._save_issue(
                        self.AGENT, "Citation Verifier",
                        f"External link redirects to different domain '{redirect_domain}': {link_url}",
                        "medium", url, pid,
                        "Verify this redirect is intentional and the destination is trustworthy.",
                        {"link_url": link_url, "redirect_domain": redirect_domain},
                    )

        # 2. Testimonial Audit (from Call B)
        for item in call_b.get("testimonial_authenticity", []):
            ai_score = item.get("ai_score", 0)
            snippet = item.get("text_snippet", "")
            reason = item.get("reason", "")
            severity = "high" if ai_score >= 75 else "medium" if ai_score >= 50 else "info"
            try:
                self.supabase.table("testimonial_audits").insert({
                    "audit_session_id": self.audit_session_id,
                    "testimonial_text": snippet[:500],
                    "page_url": url,
                    "ai_detection_confidence": ai_score,
                    "authenticity_score_0_100": 100 - ai_score,
                    "specific_details_present": ai_score < 50,
                    "flags": {"reason": reason},
                }).execute()
            except Exception:
                pass
            if ai_score >= 50:
                issues_found += self._save_issue(
                    self.AGENT, "Testimonial Audit",
                    f"Testimonial flagged as likely AI-generated (score: {ai_score}/100): \"{snippet[:100]}...\" — {reason}",
                    severity, url, pid,
                    "Replace AI-generated testimonials with verified, specific customer reviews.",
                    {"ai_score": ai_score, "snippet": snippet[:200]},
                )

        return {"issues_found": issues_found}

    async def _verify_links(self, urls: List[str]) -> List[Dict]:
        """Verify all external links concurrently via httpx."""
        async def _check(client, link_url):
            try:
                t0 = time.time()
                resp = await client.get(
                    link_url,
                    headers={"User-Agent": _BROWSER_UA},
                    follow_redirects=True,
                    timeout=self.settings.EXTERNAL_LINK_TIMEOUT_S,
                )
                response_ms = int((time.time() - t0) * 1000)
                final_url = str(resp.url)
                from urllib.parse import urlparse as _uparse
                redirect_domain = _uparse(final_url).netloc if final_url != link_url else None
                return {
                    "url": link_url,
                    "status": resp.status_code,
                    "reachable": resp.status_code < 400,
                    "response_ms": response_ms,
                    "redirect_domain": redirect_domain,
                }
            except Exception as e:
                return {"url": link_url, "status": 0, "reachable": False, "response_ms": 0, "redirect_domain": None}

        async with httpx.AsyncClient() as client:
            tasks = [_check(client, u) for u in urls]
            return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Agent 5: Fortress Sentry — Privacy & Security
# ---------------------------------------------------------------------------

_API_KEY_PATTERNS = [
    re.compile(r'AKIA[0-9A-Z]{16}'),                      # AWS Access Key
    re.compile(r'Bearer [A-Za-z0-9\-_.~+/]+=*'),          # Bearer token
    re.compile(r'eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+'),  # JWT
    re.compile(r'postgres(?:ql)?://[^\s"\']+'),            # Postgres URL
    re.compile(r'mysql://[^\s"\']+'),                      # MySQL URL
    re.compile(r'mongodb\+srv://[^\s"\']+'),               # MongoDB
    re.compile(r'[A-Za-z0-9]{32,}', re.IGNORECASE),       # Generic long token (broad)
    re.compile(r'sk-[A-Za-z0-9]{32,}'),                   # OpenAI-style key
    re.compile(r'AIza[0-9A-Za-z\-_]{35}'),                # Google API key
]

_EXIF_SENSITIVE_TAGS = {
    34853: "GPS Data",
    271: "Camera Make",
    272: "Camera Model",
    305: "Software",
    306: "DateTime",
    36867: "DateTimeOriginal",
    40962: "ImageWidth",
    40963: "ImageHeight",
}

class FortressSentry(BaseAgent):
    AGENT = "fortress_sentry"

    async def analyze(self, bundle: PageBundle, call_a: Dict, call_b: Dict) -> Dict:
        issues_found = 0
        url = bundle.url
        pid = bundle.audit_page_id

        # 1. Console Log Leaks — regex pre-filter first
        for entry in bundle.console_logs:
            text = entry.get("text", "")
            entry_type = entry.get("type", "log")
            for pattern in _API_KEY_PATTERNS:
                match = pattern.search(text)
                if match:
                    # Filter false positives: must be > 20 chars, not a URL slug or CSS class
                    matched_val = match.group()
                    if len(matched_val) > 20 and not matched_val.startswith("http"):
                        issues_found += self._save_issue(
                            self.AGENT, "Console Log Leak",
                            f"Potential sensitive data in browser console ({entry_type}): {text[:200]}",
                            "critical", url, pid,
                            "Remove all debug logging that exposes credentials or internal system details.",
                            {"console_type": entry_type, "matched_pattern": matched_val[:50]},
                        )
                        try:
                            self.supabase.table("security_console_leaks").insert({
                                "audit_session_id": self.audit_session_id,
                                "page_url": url,
                                "console_message_type": entry_type,
                                "detected_pattern_type": "regex_match",
                                "message_text": text[:500],
                                "flagged_content": matched_val[:200],
                                "severity": "critical",
                            }).execute()
                        except Exception:
                            pass
                        break

        # Also check Call B LLM-flagged console data
        for item in call_b.get("console_sensitive_data", []):
            issues_found += self._save_issue(
                self.AGENT, "Console Log Leak",
                f"LLM-detected sensitive console data: {item}",
                "critical", url, pid,
                "Audit all console.log() calls and remove before production deployment.",
            )

        # 2. Sensitive Data Masking — from Call A vision analysis
        pwd_mask = call_a.get("password_field_visible", {})
        if pwd_mask.get("detected"):
            issues_found += self._save_issue(
                self.AGENT, "Sensitive Data Masking",
                f"Password/sensitive field content is visible as plaintext: {pwd_mask.get('description', '')}",
                "critical", url, pid,
                "Ensure all password fields use type='password'. Never override masking with CSS.",
            )

        # 3. EXIF Metadata — download and parse images via Pillow
        exif_issues = await self._check_exif(bundle.image_urls, url)
        for issue in exif_issues:
            issues_found += self._save_issue(
                self.AGENT, "EXIF Metadata Leak",
                issue["detail"],
                issue["severity"], url, pid,
                "Strip EXIF data from all images before uploading using tools like ImageOptim or ExifTool.",
                {"image_url": issue["image_url"], "exif_field": issue["field"]},
            )
            try:
                self.supabase.table("security_exif_findings").insert({
                    "audit_session_id": self.audit_session_id,
                    "image_url": issue["image_url"],
                    "exif_field_name": issue["field"],
                    "exif_value": issue["value"][:200],
                    "privacy_risk_level": issue["severity"],
                    "found_on_page": url,
                }).execute()
            except Exception:
                pass

        return {"issues_found": issues_found}

    async def _check_exif(self, image_urls: List[str], page_url: str) -> List[Dict]:
        """Download images and extract EXIF data using Pillow."""
        findings = []
        urls_to_check = image_urls[:self.settings.EXIF_MAX_IMAGES_PER_PAGE]

        async def _fetch_and_parse(img_url):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        img_url,
                        headers={"User-Agent": _BROWSER_UA},
                        timeout=10,
                        follow_redirects=True,
                    )
                    if resp.status_code != 200:
                        return []
                    content_type = resp.headers.get("content-type", "")
                    # Skip SVG and GIF (no EXIF)
                    if "svg" in content_type or "gif" in content_type:
                        return []
                    img = Image.open(io.BytesIO(resp.content))
                    exif_data = img._getexif() if hasattr(img, "_getexif") else None
                    if not exif_data:
                        return []
                    results = []
                    for tag_id, value in exif_data.items():
                        if tag_id in _EXIF_SENSITIVE_TAGS:
                            field_name = _EXIF_SENSITIVE_TAGS[tag_id]
                            severity = "critical" if tag_id == 34853 else "high" if tag_id in (271, 272) else "medium"
                            results.append({
                                "image_url": img_url,
                                "field": field_name,
                                "value": str(value),
                                "severity": severity,
                                "detail": f"Image '{img_url}' contains {field_name} EXIF data: {str(value)[:100]}",
                            })
                    return results
            except Exception:
                return []

        tasks = [_fetch_and_parse(u) for u in urls_to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                findings.extend(r)
        return findings


# ---------------------------------------------------------------------------
# Agent 6: Vision Architect — Psychology & Value
# ---------------------------------------------------------------------------

class VisionArchitect(BaseAgent):
    AGENT = "vision_architect"

    async def analyze(self, bundle: PageBundle, call_a: Dict, call_b: Dict) -> Dict:
        issues_found = 0
        url = bundle.url
        pid = bundle.audit_page_id

        # 1. Empty State Deserts (from Call A)
        empty = call_a.get("empty_state", {})
        if empty.get("detected"):
            issues_found += self._save_issue(
                self.AGENT, "Empty State Desert",
                f"Empty state page lacks motivating CTA: {empty.get('description', '')}",
                "medium", url, pid,
                "Add an onboarding prompt or 'Get Started' CTA to empty states to guide users.",
            )

        # 2. Reading Level Audit — textstat (free, zero LLM cost)
        if bundle.page_text_blocks:
            full_text = " ".join(bundle.page_text_blocks)
            try:
                fk_grade = textstat.flesch_kincaid_grade(full_text)
                fk_ease = textstat.flesch_reading_ease(full_text)
                ai_score = call_b.get("ai_generated_copy_score", 0)
                ai_explanation = call_b.get("ai_generated_copy_explanation", "")

                try:
                    self.supabase.table("reading_level_audits").insert({
                        "audit_page_id": pid,
                        "text_block_selector": "page_body",
                        "flesch_kincaid_grade_level": fk_grade,
                        "ai_pattern_score_0_100": ai_score,
                        "text_snippet": full_text[:500],
                    }).execute()
                except Exception:
                    pass

                if fk_grade > 12:
                    issues_found += self._save_issue(
                        self.AGENT, "Reading Level Audit",
                        f"Page copy reads at grade {fk_grade:.1f} level (Flesch ease: {fk_ease:.0f}/100) — too complex for general audiences.",
                        "medium", url, pid,
                        "Rewrite body copy to a grade 8-10 level. Use shorter sentences and simpler vocabulary.",
                        {"fk_grade": fk_grade, "fk_ease": fk_ease},
                    )

                if ai_score >= 70:
                    issues_found += self._save_issue(
                        self.AGENT, "Reading Level Audit",
                        f"Copy appears AI-generated (score: {ai_score}/100): {ai_explanation}",
                        "medium", url, pid,
                        "Rewrite copy with a human voice, specific details, and personal context.",
                        {"ai_score": ai_score},
                    )
            except Exception as e:
                logger.debug(f"textstat error for {url}: {e}")

        # 3. Tone Consistency (from Call A)
        tone = call_a.get("tone_sections", {})
        hero_tone = tone.get("hero_tone", "")
        body_tone = tone.get("body_tone", "")
        footer_tone = tone.get("footer_tone", "")

        if hero_tone and footer_tone:
            # Simple heuristic: flag if tone descriptors contain contradictory words
            formal_words = {"formal", "legal", "technical", "legalistic", "cold", "corporate"}
            casual_words = {"casual", "friendly", "playful", "conversational", "warm", "fun"}
            hero_formal = any(w in hero_tone.lower() for w in formal_words)
            hero_casual = any(w in hero_tone.lower() for w in casual_words)
            footer_formal = any(w in footer_tone.lower() for w in formal_words)
            footer_casual = any(w in footer_tone.lower() for w in casual_words)

            if (hero_casual and footer_formal) or (hero_formal and footer_casual):
                issues_found += self._save_issue(
                    self.AGENT, "Tone Consistency",
                    f"Tone shifts abruptly: hero is '{hero_tone}', footer is '{footer_tone}'.",
                    "medium", url, pid,
                    "Maintain a consistent voice across all sections. Use a brand tone guide.",
                    {"hero_tone": hero_tone, "body_tone": body_tone, "footer_tone": footer_tone},
                )
                try:
                    self.supabase.table("tone_analysis").insert({
                        "audit_page_id": pid,
                        "section_name": "page_overview",
                        "detected_tone": f"hero: {hero_tone} | body: {body_tone} | footer: {footer_tone}",
                        "consistency_score_0_100": 40,
                        "tone_shift_severity": "medium",
                    }).execute()
                except Exception:
                    pass

        # 4. Enhancement Strategy (from Call A)
        enhancements = call_a.get("psychology_enhancements", [])
        for i, suggestion in enumerate(enhancements[:5]):
            try:
                self.supabase.table("enhancement_strategies").insert({
                    "audit_session_id": self.audit_session_id,
                    "page_url": url,
                    "suggested_enhancement": suggestion,
                    "psychology_principle": "conversion_optimization",
                    "priority_rank": i + 1,
                    "category": "psychology",
                }).execute()
            except Exception:
                pass

        return {"issues_found": issues_found}


# ---------------------------------------------------------------------------
# Agent 7: Internal State Monitor — DOM Mutations, Performance, Personas
# ---------------------------------------------------------------------------

class InternalStateMonitor(BaseAgent):
    AGENT = "internal_state_monitor"

    async def analyze(self, bundle: PageBundle, call_a: Dict, call_b: Dict) -> Dict:
        issues_found = 0
        url = bundle.url
        pid = bundle.audit_page_id

        # 1. DOM Mutation Observer — ghost updates
        if bundle.dom_mutations:
            significant_mutations = [
                m for m in bundle.dom_mutations
                if m.get("added_nodes", 0) + m.get("removed_nodes", 0) > 5
            ]
            if significant_mutations:
                # Ghost update: significant structural DOM change with no visible layout shift
                if not bundle.mobile_layout_shift_detected:
                    for mutation in significant_mutations[:3]:
                        issues_found += self._save_issue(
                            self.AGENT, "DOM Ghost Update",
                            f"Significant DOM mutation ({mutation.get('added_nodes')} nodes added, {mutation.get('removed_nodes')} removed) on element '{mutation.get('selector')}' with no visible visual change — possible shadow background process.",
                            "info", url, pid,
                            "Investigate background scripts or data-fetching that modifies the DOM invisibly.",
                            {"mutation": mutation},
                        )
                        try:
                            self.supabase.table("dom_mutations").insert({
                                "audit_page_id": pid,
                                "mutation_type": mutation.get("type", "unknown"),
                                "element_selector": mutation.get("selector", ""),
                                "visual_change_detected": False,
                            }).execute()
                        except Exception:
                            pass

        # 2. Performance Baseline — already stored by navigator, flag in issues too
        if (
            bundle.baseline_load_time_ms is not None
            and bundle.load_time_ms > bundle.baseline_load_time_ms + self.settings.PERFORMANCE_BASELINE_THRESHOLD_MS
        ):
            diff_ms = bundle.load_time_ms - bundle.baseline_load_time_ms
            issues_found += self._save_issue(
                self.AGENT, "Performance Bottleneck",
                f"Page took {bundle.load_time_ms}ms — {diff_ms}ms slower than baseline ({bundle.baseline_load_time_ms}ms).",
                "high", url, pid,
                "Profile network requests and rendering. Check for large uncompressed assets, third-party scripts, or server latency.",
                {"load_time_ms": bundle.load_time_ms, "baseline_ms": bundle.baseline_load_time_ms, "diff_ms": diff_ms},
            )

        # 3. Persona — Frustrated User (rage clicks)
        rage = call_a.get("rage_click_result_issue", {})
        if rage.get("detected"):
            issues_found += self._save_issue(
                self.AGENT, "User Persona Simulation",
                f"Frustrated user (rage clicks): {rage.get('description', '')}",
                "high", url, pid,
                "Add click debouncing, loading state, or disable the button after first click to prevent duplicate submissions.",
            )
        try:
            self.supabase.table("persona_interactions").insert({
                "audit_page_id": pid,
                "persona_type": "frustrated_user",
                "issues_triggered": {"rage_click_issue": rage},
            }).execute()
        except Exception:
            pass

        # 4. Persona — Confused User (tooltip/help availability)
        if bundle.persona_confused_hover_result:
            total = len(bundle.persona_confused_hover_result)
            no_tooltip = sum(1 for r in bundle.persona_confused_hover_result if not r.get("tooltip_found"))
            pct_missing = (no_tooltip / total * 100) if total > 0 else 0

            if pct_missing > 70 and total > 3:
                issues_found += self._save_issue(
                    self.AGENT, "User Persona Simulation",
                    f"Confused user simulation: {no_tooltip}/{total} interactive elements ({pct_missing:.0f}%) have no tooltip or aria-label. A confused user gets no contextual help.",
                    "medium", url, pid,
                    "Add title attributes or aria-label to all interactive elements. Consider adding tooltip components for non-obvious actions.",
                    {"no_tooltip_count": no_tooltip, "total_elements": total},
                )
            try:
                self.supabase.table("persona_interactions").insert({
                    "audit_page_id": pid,
                    "persona_type": "confused_user",
                    "issues_triggered": {
                        "elements_without_tooltip": no_tooltip,
                        "total_elements": total,
                        "missing_pct": pct_missing,
                    },
                }).execute()
            except Exception:
                pass

        return {"issues_found": issues_found}
