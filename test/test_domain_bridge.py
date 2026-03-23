from __future__ import annotations

import json
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

    def test_enqueue_also_inserts_domain_into_infrastructure_registry(self) -> None:
        result = domain_bridge.enqueue_spamhaus_domains(
            ["Example.com"],
            source_job_id="job-789",
            domain_records=[
                {
                    "domain": "Example.com",
                    "status": "ok",
                    "reputation_score": "12.5",
                    "registrar": "Example Registrar",
                    "job_id": "job-789",
                    "source": "cache",
                }
            ],
            db_path=self.db_path,
        )

        self.assertEqual(result["infra_registry_inserted"], 1)
        self.assertEqual(result["infra_registry_updated"], 0)

        with domain_bridge._connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload FROM app_storage WHERE storage_key = ?",
                (domain_bridge.INFRA_STORAGE_KEY,),
            ).fetchone()

        self.assertIsNotNone(row)
        payload = json.loads(row["payload"])
        self.assertEqual(len(payload["domainRegistry"]), 1)
        entry = payload["domainRegistry"][0]
        self.assertEqual(entry["domain"], "example.com")
        self.assertEqual(entry["provider"], "spamhostshaker")
        self.assertEqual(entry["expiryDate"], "")
        self.assertEqual(entry["accountUser"], "")
        self.assertEqual(entry["linkedIpId"], "")
        self.assertIn("Push it from spamhost Shaker", entry["note"])
        self.assertIn("Reputation score: 12.5", entry["note"])

    def test_enqueue_updates_existing_registry_note_without_duplicate_insert(self) -> None:
        domain_bridge.sync_spamhaus_domains_to_infra_registry(["example.com"], db_path=self.db_path)

        result = domain_bridge.enqueue_spamhaus_domains(
            ["example.com"],
            domain_records=[{"domain": "example.com", "status": "ok", "reputation_score": "77"}],
            db_path=self.db_path,
        )

        self.assertEqual(result["infra_registry_inserted"], 0)
        self.assertEqual(result["infra_registry_updated"], 1)

        with domain_bridge._connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT payload FROM app_storage WHERE storage_key = ?",
                (domain_bridge.INFRA_STORAGE_KEY,),
            ).fetchone()

        payload = json.loads(row["payload"])
        self.assertEqual(len(payload["domainRegistry"]), 1)
        self.assertIn("Reputation score: 77", payload["domainRegistry"][0]["note"])
