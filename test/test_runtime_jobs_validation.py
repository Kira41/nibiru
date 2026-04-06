from __future__ import annotations

import copy
import os
import unittest
import sys
import types
from types import SimpleNamespace
from unittest.mock import patch

from test import support_fake_deps

support_fake_deps.install()

for _name in ("script1", "script2", "script3", "script4", "script5"):
    if _name not in sys.modules:
        sys.modules[_name] = types.ModuleType(_name)

import nibiru  # noqa: E402


class RuntimeJobsValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._jobs_backup = copy.deepcopy(nibiru.JOBS)
        self._dashboard_backup = copy.deepcopy(nibiru.DASHBOARD_DATA)

    def tearDown(self) -> None:
        nibiru.JOBS[:] = self._jobs_backup
        nibiru.DASHBOARD_DATA.clear()
        nibiru.DASHBOARD_DATA.update(self._dashboard_backup)

    def _start_send_job(self) -> str:
        fake_form = {
            "campaign_id": "cmp-runtime-validation",
            "permission_ok": "on",
            "from_email": "sender@example.com",
            "from_name": "Runtime Tester",
            "subject": "Runtime validation",
            "smtp_host": "smtp.example.com",
            "smtp_port": "587",
            "chunk_size": "100",
            "maillist": "a@example.net\nb@example.net\nc@example.net",
        }
        existing_ids = {str(row.get("id") or "") for row in nibiru.JOBS if isinstance(row, dict)}
        with patch.object(nibiru, "request", SimpleNamespace(form=fake_form, is_json=False, json={})):
            _ = nibiru.start_send_job()
        new_jobs = [row for row in nibiru.JOBS if isinstance(row, dict) and str(row.get("id") or "") not in existing_ids]
        self.assertTrue(new_jobs)
        created_job = str(new_jobs[0].get("id") or "")
        self.assertTrue(created_job)
        return created_job

    def test_runtime_flow_and_pmta_modes(self) -> None:
        created_job = self._start_send_job()

        # 1-2: start send and verify meaningful job object
        job_obj = nibiru.get_job(created_job)
        self.assertIsNotNone(job_obj)
        assert job_obj is not None
        self.assertEqual(job_obj["status"], "queued")
        self.assertGreaterEqual(int(job_obj.get("total") or 0), 3)
        self.assertTrue(job_obj.get("runtime_logs"))

        # 3: /api/jobs returns created job
        with patch.object(nibiru, "jsonify", side_effect=lambda payload: payload):
            jobs_payload = nibiru.api_jobs()
        job_ids = [row.get("id") for row in jobs_payload["jobs"]]
        self.assertIn(created_job, job_ids)

        # 4 + 7 + 8 + 9: /api/job detail has populated fields and diagnostics surfaced
        with patch.object(nibiru, "jsonify", side_effect=lambda payload: payload):
            detail = nibiru.api_job(created_job)
        self.assertEqual(detail["job_id"], created_job)
        self.assertIn("totals", detail)
        self.assertIn("pmta_live", detail)
        self.assertIn("pmta_diag", detail)
        self.assertIn("bridge_state", detail)
        self.assertIn("bridge_mode", detail)
        self.assertIsInstance(detail.get("logs"), list)
        self.assertGreater(len(detail["logs"]), 0)
        self.assertIn("reason", detail["pmta_live"])
        self.assertIn("errors_sample", detail["pmta_diag"])

        # 5: Jobs page sections have non-empty values/content blocks
        jobs_html = nibiru.JOBS_PAGE_HTML
        self.assertIn("PMTA Live Panel", jobs_html)
        self.assertIn("Outcomes (PMTA accounting)", jobs_html)
        self.assertIn("Bridge snapshot", jobs_html)

        # 6a: SSH unavailable path
        nibiru.DASHBOARD_DATA.setdefault("message_form", {})["ssh_host"] = ""
        nibiru.DASHBOARD_DATA.setdefault("message_form", {})["ssh_user"] = ""
        with patch.dict(os.environ, {"PMTA_SSH_HOST": "", "PMTA_SSH_USER": ""}, clear=False):
            with patch.object(nibiru, "jsonify", side_effect=lambda payload: payload):
                ssh_unavailable = nibiru.api_accounting_ssh_status()
        self.assertFalse(ssh_unavailable["ok"])
        self.assertIn("not configured", ssh_unavailable["bridge"].get("last_error", "").lower())

        # 6b: SSH available path (mock successful pmta outputs)
        nibiru.DASHBOARD_DATA.setdefault("message_form", {})["ssh_host"] = "ops.example.internal"
        nibiru.DASHBOARD_DATA.setdefault("message_form", {})["ssh_user"] = "pmtaops"

        def fake_run_ssh_command(_runtime_config, remote_command):
            command = str(remote_command).lower()
            if "show status" in command:
                return {
                    "stdout": (
                        "spool rcpt 12 msg 3\n"
                        "queue rcpt 9 msg 2\n"
                        "smtp in 4 out 5\n"
                        "last minute in 20 out 18\n"
                        "last hour in 700 out 640\n"
                        "sent 18 delivered 16 bounced 1 deferred 1 complained 0\n"
                    )
                }
            if "topqueues" in command:
                return {"stdout": "queue rcpt\nexample.com 7\n"}
            return {"stdout": "defer: temporary 421\n"}

        with patch("nibiru.script6.run_ssh_command", side_effect=fake_run_ssh_command):
            with patch.object(nibiru, "jsonify", side_effect=lambda payload: payload):
                ssh_available = nibiru.api_accounting_ssh_status()
            with patch.object(nibiru, "jsonify", side_effect=lambda payload: payload):
                detail_with_ssh = nibiru.api_job(created_job)

        self.assertTrue(ssh_available["ok"])
        self.assertTrue(detail_with_ssh["bridge_state"].get("connected"))
        self.assertTrue(detail_with_ssh["pmta_live"].get("ok"))
        self.assertEqual(detail_with_ssh["pmta_live"].get("spool_recipients"), 12)
        self.assertEqual(detail_with_ssh["pmta_diag"].get("queue_deferrals"), 1)


if __name__ == "__main__":
    unittest.main()
