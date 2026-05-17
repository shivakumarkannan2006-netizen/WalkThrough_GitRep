import unittest

from config import Settings


class TestAuditProfiles(unittest.TestCase):
    def test_quick_profile_disables_interactions(self):
        s = Settings()
        s.AUDIT_PROFILE = "quick"
        self.assertTrue(s.is_quick_profile())
        self.assertFalse(s.run_interaction_phases())
        self.assertEqual(s.max_cta_clicks(), 0)

    def test_standard_profile_caps(self):
        s = Settings()
        s.AUDIT_PROFILE = "standard"
        self.assertEqual(s.max_cta_clicks(), 3)
        self.assertEqual(s.max_forms(), 1)
        self.assertEqual(s.max_form_input_types(), 2)
        self.assertEqual(s.max_hovers(), 8)
        self.assertFalse(s.use_sitemap_seed())

    def test_deep_profile_sitemap(self):
        s = Settings()
        s.AUDIT_PROFILE = "deep"
        self.assertTrue(s.use_sitemap_seed())
        self.assertEqual(s.max_cta_clicks(), 5)


if __name__ == "__main__":
    unittest.main()
