import unittest
from unittest.mock import MagicMock

from crew import (
    CALL_A_SCHEMA,
    CALL_B_SCHEMA,
    CrewOrchestrator,
    _interaction_ambiguous,
    _parse_json_response,
    _validate_call_a,
    _validate_call_b,
)
from config import Settings
from navigator import PageBundle


def _minimal_bundle(**kwargs) -> PageBundle:
    defaults = dict(
        audit_page_id="test-page-id",
        url="https://example.com/",
        page_title="Test",
        meta_description="Test meta",
        http_status_code=200,
        load_time_ms=100,
        authenticated=False,
        baseline_load_time_ms=100,
        axe_tree=None,
        page_html="<html></html>",
        page_text_blocks=["Enough text block for analysis here."],
        screenshot_desktop_b64="",
        screenshot_mobile_b64="",
        screenshot_fout_b64="",
        console_logs=[],
        cookies_on_load=[],
        viewport_overflow={},
        mobile_layout_shift_detected=False,
        interactive_element_bounding_boxes=[],
        dom_mutations=[],
        spa_route_urls=[],
        external_links=[],
        image_urls=[],
        prices_found=[],
        contact_info_found=[],
        testimonial_blocks=[],
        anchor_click_results=[],
        click_interaction_timings=[],
        password_field_screenshots=[],
        form_interaction_results=[],
        persona_frustrated_screenshot_b64="",
        persona_confused_hover_result=[],
        back_button_result={},
    )
    defaults.update(kwargs)
    return PageBundle(**defaults)


class TestCrewHelpers(unittest.TestCase):
    def test_parse_json_response_strips_markdown(self):
        raw = 'Here is JSON:\n{"contrast_issues": [], "layout_overlaps": []}'
        parsed = _parse_json_response(raw)
        self.assertIn("contrast_issues", parsed)

    def test_validate_call_a_requires_keys(self):
        self.assertFalse(_validate_call_a({}))
        obj_keys = {
            "mobile_keyboard_collision", "horizontal_overflow_visual", "empty_state",
            "password_field_visible", "back_button_result_issue", "rage_click_result_issue",
            "fout_detected",
        }
        list_keys = {
            "contrast_issues", "layout_overlaps", "placeholder_text", "dark_patterns",
            "general_polish_issues", "psychology_enhancements",
        }
        minimal = {}
        for k in CALL_A_SCHEMA["required"]:
            if k in list_keys:
                minimal[k] = []
            elif k == "tone_sections":
                minimal[k] = {"hero_tone": "", "body_tone": "", "footer_tone": ""}
            elif k in obj_keys:
                minimal[k] = {"detected": False, "description": ""}
        self.assertTrue(_validate_call_a(minimal))

    def test_validate_call_b_requires_keys(self):
        self.assertFalse(_validate_call_b({}))
        minimal = {k: [] for k in CALL_B_SCHEMA["required"]}
        minimal["ai_generated_copy_score"] = 0
        minimal["ai_generated_copy_explanation"] = ""
        minimal["reading_level_grade"] = 8.0
        self.assertTrue(_validate_call_b(minimal))

    def test_interaction_ambiguous_on_slow_cta(self):
        bundle = _minimal_bundle(
            click_interaction_timings=[{"response_ms": 800, "had_spinner": False, "snapshot_b64": "x"}]
        )
        self.assertTrue(_interaction_ambiguous(bundle))

    def test_llm_gating_skips_thin_pages_for_call_b(self):
        orch = CrewOrchestrator(supabase_client=MagicMock(), audit_session_id="sess")
        orch._model = MagicMock()
        thin = _minimal_bundle(page_text_blocks=["short"], testimonial_blocks=[], prices_found=[])
        self.assertFalse(orch._should_run_call_b(thin))

    def test_quick_profile_skips_llm(self):
        orch = CrewOrchestrator(supabase_client=MagicMock(), audit_session_id="sess")
        orch.settings.AUDIT_PROFILE = "quick"
        bundle = _minimal_bundle(
            screenshot_desktop_b64="abc",
            page_text_blocks=["a"] * 10,
        )
        self.assertFalse(orch._should_run_call_a(bundle))
        self.assertFalse(orch._should_run_call_b(bundle))


if __name__ == "__main__":
    unittest.main()
