from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from project_context_provider import ProjectContextProvider


class StubRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def context_for(
        self,
        scope: str,
        path: str,
        task: str,
        max_tokens: int = 8_000,
        max_files: int = 19,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "scope": scope,
                "path": path,
                "task": task,
                "max_tokens": max_tokens,
                "max_files": max_files,
            }
        )
        return {
            "items": [{"path": "src/app.py", "content": "print('ok')"}],
            "estimated_tokens": 4,
            "file_count": 1,
        }


class ProjectContextProviderTests(unittest.TestCase):
    def test_build_normalizes_input_and_delegates_to_context_runtime(self):
        runtime = StubRuntime()
        provider = ProjectContextProvider(runtime)

        result = provider.build(
            scope=" WORKSPACE ",
            path=" demo ",
            task="  corrigir   login  ",
        )

        self.assertEqual("workspace", result["scope"])
        self.assertEqual("demo", result["path"])
        self.assertEqual("corrigir login", result["task"])
        self.assertEqual("project-intelligence", result["provider"])
        self.assertEqual(1, len(runtime.calls))
        self.assertEqual(8_000, runtime.calls[0]["max_tokens"])
        self.assertEqual(19, runtime.calls[0]["max_files"])

    def test_build_hard_caps_requested_budget(self):
        runtime = StubRuntime()
        provider = ProjectContextProvider(runtime)

        result = provider.build(
            scope="workspace",
            path="demo",
            task="analisar projeto",
            max_tokens=50_000,
            max_files=100,
        )

        self.assertEqual({"max_tokens": 8_000, "max_files": 19}, result["budget"])
        self.assertEqual(8_000, runtime.calls[0]["max_tokens"])
        self.assertEqual(19, runtime.calls[0]["max_files"])

    def test_build_rejects_empty_scope_or_task(self):
        runtime = StubRuntime()
        provider = ProjectContextProvider(runtime)

        with self.assertRaises(ValueError):
            provider.build(scope="", path=".", task="analisar")

        with self.assertRaises(ValueError):
            provider.build(scope="workspace", path=".", task="   ")


if __name__ == "__main__":
    unittest.main()
