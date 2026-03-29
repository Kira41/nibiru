from __future__ import annotations

import ast
import unittest
from pathlib import Path


class NibiruDomainAuthLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source_path = Path(__file__).resolve().parent.parent / "nibiru.py"
        cls.source = source_path.read_text(encoding="utf-8")
        cls.module = ast.parse(cls.source)

    def _find_function(self, name: str) -> ast.FunctionDef:
        for node in self.module.body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        self.fail(f"Expected function {name} in nibiru.py")

    def test_classify_txt_policy_status_exists_with_dns_error_marker(self) -> None:
        fn = self._find_function("_classify_txt_policy_status")
        body = ast.unparse(fn)
        self.assertIn("dns_error", body)
        self.assertIn("policy_mismatch", body)
        self.assertIn("missing_record", body)

    def test_check_domain_auth_records_includes_reason_fields(self) -> None:
        fn = self._find_function("_check_domain_auth_records")
        body = ast.unparse(fn)
        self.assertIn("'reason': spf_reason", body.replace('"', "'"))
        self.assertIn("'reason': dkim_reason", body.replace('"', "'"))
        self.assertIn("'reason': dmarc_reason", body.replace('"', "'"))
        self.assertIn("selector_not_found", body)


if __name__ == "__main__":
    unittest.main()
