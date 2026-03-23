from __future__ import annotations

from support_fake_deps import install
install()

import http.server
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import script5


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class TrackerWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_db_path = script5.DB_PATH
        self._tmpdir = tempfile.TemporaryDirectory()
        script5.DB_PATH = Path(self._tmpdir.name) / 'tracker-test.db'
        script5.init_db()

    def tearDown(self) -> None:
        script5.DB_PATH = self._original_db_path
        self._tmpdir.cleanup()

    def _start_fixture_server(self) -> tuple[socketserver.TCPServer, threading.Thread, str]:
        fixture_dir = Path(__file__).resolve().parent / 'fixtures'
        handler = lambda *args, **kwargs: QuietHTTPRequestHandler(*args, directory=str(fixture_dir), **kwargs)
        server = socketserver.TCPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f'http://127.0.0.1:{server.server_address[1]}'
        return server, thread, base_url

    def test_parse_emails_normalizes_and_deduplicates(self) -> None:
        raw = 'User@One.com, user@one.com\ninvalid\nSecond@Two.com\n'
        self.assertEqual(script5.parse_emails(raw), ['user@one.com', 'second@two.com'])

    def test_analyze_stay_data_with_local_fixture(self) -> None:
        script5.upsert_email_mappings(['alpha@example.com', 'beta@example.com'])
        alpha_id = script5.email_to_10_digits('alpha@example.com')
        beta_id = script5.email_to_10_digits('beta@example.com')
        self.assertEqual(alpha_id, '1276758214')
        self.assertEqual(beta_id, '8430913098')

        server, thread, base_url = self._start_fixture_server()
        try:
            with mock.patch.object(script5, 'is_bot_ip', return_value=False):
                analysis = script5.analyze_stay_data(base_url)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(analysis['url_count'], 1)
        self.assertEqual(analysis['found_count'], 3)
        self.assertEqual(analysis['matched_count'], 2)
        self.assertEqual(analysis['new_matched_count'], 2)
        self.assertEqual(analysis['unmatched_ids'], ['9999999999'])
        self.assertEqual([row['email'] for row in analysis['matches']], ['beta@example.com', 'alpha@example.com'])
        self.assertEqual(analysis['domain_stats'][0]['domain'], 'outlook.office.com')
        self.assertEqual(analysis['domain_stats'][1]['domain'], 'mail.google.com')
