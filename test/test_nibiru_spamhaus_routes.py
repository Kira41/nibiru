from __future__ import annotations

import ast
import unittest
from pathlib import Path


class NibiruSpamhausRouteTests(unittest.TestCase):
    def test_cache_results_route_is_exposed_in_nibiru(self) -> None:
        source_path = Path(__file__).resolve().parent.parent / "nibiru.py"
        module = ast.parse(source_path.read_text(encoding="utf-8"))

        target = None
        for node in module.body:
            if isinstance(node, ast.FunctionDef) and node.name == "spamhaus_api_cache_results":
                target = node
                break

        self.assertIsNotNone(target, "Expected spamhaus_api_cache_results() in nibiru.py")

        route_decorators = [
            decorator
            for decorator in target.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and isinstance(decorator.func.value, ast.Name)
            and decorator.func.value.id == "app"
            and decorator.func.attr == "get"
        ]
        self.assertTrue(route_decorators, "Expected an @app.get decorator on spamhaus_api_cache_results()")
        self.assertEqual(route_decorators[0].args[0].value, "/tools/spamhaus/api/cache-results")

        self.assertEqual(len(target.body), 1)
        self.assertIsInstance(target.body[0], ast.Return)
        self.assertEqual(
            ast.unparse(target.body[0].value),
            "script1.api_cache_results()",
        )


if __name__ == "__main__":
    unittest.main()
