from __future__ import annotations

import ast
import unittest
from pathlib import Path


class StartSendJobRecipientsTests(unittest.TestCase):
    def test_start_send_job_reads_recipients_field_before_legacy_maillist(self) -> None:
        source_path = Path(__file__).resolve().parent.parent / "nibiru.py"
        module = ast.parse(source_path.read_text(encoding="utf-8"))

        target = None
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name == "start_send_job":
                target = node
                break

        self.assertIsNotNone(target, "Expected start_send_job() in nibiru.py")
        body_source = ast.unparse(target)
        self.assertIn("request.form.get('recipients')", body_source)
        self.assertIn("request.form.get('maillist')", body_source)
        self.assertIn("re.split('[\\\\n,;]+', recipients_raw)", body_source)


if __name__ == "__main__":
    unittest.main()
