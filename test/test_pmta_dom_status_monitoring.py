from __future__ import annotations

import ast
import unittest
from pathlib import Path


class PmtaDomStatusMonitoringTests(unittest.TestCase):
    def test_jobs_monitoring_prefers_dom_status_and_parses_dom_keys(self) -> None:
        source_path = Path(__file__).resolve().parent.parent / "nibiru.py"
        module = ast.parse(source_path.read_text(encoding="utf-8"))

        target = None
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name == "load_pmta_monitor_snapshot":
                target = node
                break

        self.assertIsNotNone(target, "Expected load_pmta_monitor_snapshot() in nibiru.py")
        body_source = ast.unparse(target)
        self.assertIn("--dom show status", body_source)
        self.assertIn("status.queue.smtp.rcp", body_source)
        self.assertIn("status.conn.smtpIn.cur", body_source)
        self.assertIn("status.traffic.lastMin.out.rcp", body_source)


if __name__ == "__main__":
    unittest.main()
