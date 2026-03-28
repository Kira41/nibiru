from __future__ import annotations

import ast
import unittest
from pathlib import Path


class NibiruSendJobLinkingTests(unittest.TestCase):
    def test_build_job_detail_links_sender_and_snapshot_logs(self) -> None:
        source_path = Path(__file__).resolve().parent.parent / "nibiru.py"
        module = ast.parse(source_path.read_text(encoding="utf-8"))

        target = None
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name == "build_job_detail":
                target = node
                break

        self.assertIsNotNone(target, "Expected build_job_detail() in nibiru.py")
        body_source = ast.unparse(target)
        self.assertIn("send_snapshot", body_source)
        self.assertIn("sender_label", body_source)
        self.assertIn("'sender': sender_label", body_source)
        self.assertIn("Subject snapshot", body_source)
        self.assertIn("SMTP host snapshot", body_source)
        self.assertIn("send→job link", body_source)
        self.assertIn("send_debug", body_source)
        self.assertIn("send_job_relation_logs", body_source)


if __name__ == "__main__":
    unittest.main()
