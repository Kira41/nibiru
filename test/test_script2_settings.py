from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test.support_fake_deps import install

install()

import script2


class Script2SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_db_path = script2.DB_PATH
        self._tmpdir = tempfile.TemporaryDirectory()
        script2.DB_PATH = Path(self._tmpdir.name) / "script2-test.db"
        script2.init_db()

    def tearDown(self) -> None:
        script2.DB_PATH = self._original_db_path
        self._tmpdir.cleanup()

    def test_settings_round_trip_uses_database_api(self) -> None:
        payload = {
            "groupCategory": "provider",
            "groupMethod": "domain",
            "rememberSettingsMode": True,
            "sortMode": "count-desc",
        }

        saved = script2.save_settings_payload(payload)
        self.assertEqual(saved, payload)
        self.assertTrue(script2.DB_PATH.exists())

        self.assertEqual(script2.load_saved_settings(), payload)

        with script2.get_db_connection() as conn:
            conn.execute("DELETE FROM app_storage WHERE storage_key = ?", (script2.SETTINGS_STORAGE_KEY,))
            conn.commit()

        self.assertEqual(script2.load_saved_settings(), {})


if __name__ == "__main__":
    unittest.main()
