from __future__ import annotations

import ast
import unittest
from pathlib import Path


class JobsPreviewLinkingTests(unittest.TestCase):
    def test_jobs_preview_uses_real_job_id_and_created_job_query(self) -> None:
        source_path = Path(__file__).resolve().parent.parent / "nibiru.py"
        module = ast.parse(source_path.read_text(encoding="utf-8"))

        preview_builder = None
        jobs_page = None
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name == "_build_jobs_send_preview":
                preview_builder = node
            if isinstance(node, ast.FunctionDef) and node.name == "jobs_page":
                jobs_page = node

        self.assertIsNotNone(preview_builder, "Expected _build_jobs_send_preview()")
        self.assertIsNotNone(jobs_page, "Expected jobs_page()")

        preview_source = ast.unparse(preview_builder)
        jobs_page_source = ast.unparse(jobs_page)

        self.assertIn("preferred_job_id", preview_source)
        self.assertIn("latest_campaign_job", preview_source)
        self.assertIn("selected_job", preview_source)
        self.assertIn("'job_id': job_id", preview_source)
        self.assertIn("'status': status", preview_source)

        self.assertIn("created_job", jobs_page_source)
        self.assertIn("_build_jobs_send_preview(created_job)", jobs_page_source)


if __name__ == "__main__":
    unittest.main()
