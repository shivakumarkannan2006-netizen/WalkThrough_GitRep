import unittest
from pathlib import Path
from unittest.mock import MagicMock

from navigator import ShieldNavigator


class TestNavigatorLinks(unittest.TestCase):
    def setUp(self):
        self.nav = ShieldNavigator(
            target_url="https://fixture.test/index.html",
            audit_session_id="test-session",
            supabase_client=MagicMock(),
        )

    def test_extract_links_from_anchor_and_data_href(self):
        html = """
        <html><body>
          <a href="/about">About</a>
          <span data-href="/pricing">Pricing</span>
          <a href="#section">Skip</a>
          <a href="mailto:a@b.com">Email</a>
        </body></html>
        """
        urls = self.nav._extract_links_from_html(html, "https://fixture.test/index.html")
        self.assertTrue(any("about" in u for u in urls))
        self.assertTrue(any("pricing" in u for u in urls))
        self.assertFalse(any("mailto" in u for u in urls))

    def test_normalize_url_strips_fragment(self):
        self.assertEqual(
            self.nav._normalize_url("https://fixture.test/page#section"),
            "https://fixture.test/page",
        )

    def test_visited_sets_are_separate_per_auth_context(self):
        self.assertIsNot(self.nav.visited_unauth, self.nav.visited_auth)
        self.nav.visited_unauth.add("https://fixture.test/a")
        self.assertNotIn("https://fixture.test/a", self.nav.visited_auth)


if __name__ == "__main__":
    unittest.main()
