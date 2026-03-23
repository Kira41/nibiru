from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import domain_bridge


class DomainBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "infra-bridge.db"
        domain_bridge.init_polling_db(self.db_path)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_enqueue_and_list_pending_domains(self) -> None:
        result = domain_bridge.enqueue_spamhaus_domains(
            ["Example.com", "example.com", "Another.net"],
            source_job_id="job-123",
            note="Queued from Spamhaus",
            db_path=self.db_path,
        )

        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["reactivated"], 0)
        self.assertEqual(result["queued_domains"], ["example.com", "another.net"])

        queue = domain_bridge.list_spamhaus_queue(statuses=["pending"], db_path=self.db_path)
        self.assertEqual([item["domain"] for item in queue], ["another.net", "example.com"])
        self.assertTrue(all(item["status"] == "pending" for item in queue))

    def test_consumed_domain_can_be_reactivated(self) -> None:
        domain_bridge.enqueue_spamhaus_domains(["reactivate.me"], db_path=self.db_path)
        updated = domain_bridge.mark_queue_domains_consumed(["reactivate.me"], db_path=self.db_path)
        self.assertEqual(updated, 1)

        result = domain_bridge.enqueue_spamhaus_domains(
            ["reactivate.me"],
            source_job_id="job-456",
            db_path=self.db_path,
        )
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["reactivated"], 1)

        queue = domain_bridge.list_spamhaus_queue(db_path=self.db_path)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["domain"], "reactivate.me")
        self.assertEqual(queue[0]["status"], "pending")
