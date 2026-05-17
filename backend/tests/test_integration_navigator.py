import asyncio
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from config import Settings
from navigator import ShieldNavigator

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "site"
INDEX_URL = (FIXTURE_DIR / "index.html").as_uri()


class TestNavigatorIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not FIXTURE_DIR.exists():
            raise unittest.SkipTest("Fixture site missing")

    def test_bfs_discovers_multiple_local_pages_quick_profile(self):
        async def run():
            settings = Settings()
            settings.AUDIT_PROFILE = "quick"
            settings.MAX_PAGES_PER_AUDIT = 10
            settings.BFS_TIMEOUT_SECONDS = 120
            settings.ENABLE_SCREENSHOTS = False
            settings.ENABLE_PERSONAS = False

            nav = ShieldNavigator(
                target_url=INDEX_URL,
                audit_session_id="integration-test",
                supabase_client=MagicMock(),
            )
            nav.settings = settings
            insert_mock = MagicMock()
            insert_mock.execute.return_value = MagicMock(data=[{"id": "page-1"}])
            nav.supabase.table.return_value.insert.return_value = insert_mock
            nav.broadcast = lambda msg: None

            pages = await nav.start_traversal()
            urls = {p.url for p in pages}
            self.assertGreaterEqual(len(pages), 1)
            self.assertTrue(any("index.html" in u for u in urls))

        asyncio.run(run())

    def test_bfs_timeout_flag(self):
        async def run():
            settings = Settings()
            settings.AUDIT_PROFILE = "quick"
            settings.BFS_TIMEOUT_SECONDS = 0
            settings.ENABLE_SCREENSHOTS = False

            nav = ShieldNavigator(
                target_url=INDEX_URL,
                audit_session_id="timeout-test",
                supabase_client=MagicMock(),
            )
            nav.settings = settings
            nav._traversal_start = __import__("time").time() - 10
            self.assertTrue(nav._bfs_time_exceeded())

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
