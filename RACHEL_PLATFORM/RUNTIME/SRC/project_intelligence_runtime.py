from __future__ import annotations

import ast
import fnmatch
import json
import re
import tomllib
from pathlib import Path
from typing import Any, Iterable

from bran_cognitive import CognitiveMemory
from filesystem_runtime import FilesystemRuntime


MAX_PROJECT_FILES = 2_000
MAX_INDEX_BYTES = 2_000_000
MAX_SYMBOLS = 5_000
MAX_RESULTS = 100

DEFAULT_IGNORES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".next",
    ".nuxt",
    ".turbo",
    "dist",
    "build",
    "target",
    "coverage",
}

TEXT_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".json", ".toml", ".yaml", ".yml", ".md", ".txt", ".html", ".css",
    ".scss", ".rs", ".go", ".java", ".kt", ".kts", ".c", ".h", ".cpp",
    ".hpp", ".cs", ".php", ".rb", ".sh", ".ps1", ".sql", ".vue", ".svelte",
}

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".vue": "vue",
    ".svelte": "svelte",
}

INSTRUCTION_FILES = (
    ".rachel/instructions.md",
    "RACHEL.md",
    "AGENTS.md",
    "CLAUDE.md",
)


class ProjectIntelligenceError(RuntimeError):
    pass


class IgnoreRules:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.patterns: list[str] = []
        gitignore = root / ".gitignore"
        if gitignore.is_file():
            try:
                for raw in gitignore.read_text(encoding="utf-8").splitlines():
                    value = raw.strip()
                    if value and not value.startswith("#") and not value.startswith("!"):
                        self.patterns.append(value)
            except (OSError, UnicodeDecodeError):
                pass

    def ignored(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError:
            return True
        if not relative or relative == ".":
            return False
        parts = Path(relative).parts
        if any(part in DEFAULT_IGNORES for part in parts):
            return True
        for pattern in self.patterns:
            normalized = pattern.replace("\\", "/").lstrip("/")
            if normalized.endswith("/"):
                normalized = normalized.rstrip("/")
                if normalized in parts or relative.startswith(normalized + "/"):
                    return True
            if fnmatch.fnmatch(relative, normalized) or fnmatch.fnmatch(path.name, normalized):
                return True
        return False


class ProjectIntelligenceRuntime:
    """Builds bounded, reusable project context over Cyber-governed filesystem scopes."""

    def __init__(
        self,
        filesystem: FilesystemRuntime | None = None,
        memory: CognitiveMemory | None = None,
    ) -> None:
        self.filesystem = filesystem or FilesystemRuntime()
        self.memory = memory or CognitiveMemory()

    def root(self, scope: str, path: str = ".") -> Path:
        root = self.filesystem.target(scope, path)
        if not root.is_dir():
            raise ProjectIntelligenceError("Project directory not found")
        return root

    def _files(self, root: Path) -> list[Path]:
        rules = IgnoreRules(root)
        selected: list[Path] = []
        for item in sorted(root.rglob("*"), key=lambda value: value.as_posix().casefold()):
            if len(selected) >= MAX_PROJECT_FILES:
                break
            if rules.ignored(item) or item.is_symlink() or not item.is_file():
                continue
            try:
                if item.stat().st_size > MAX_INDEX_BYTES:
                    continue
            except OSError:
                continue
            selected.append(item)
        return selected

    @staticmethod
    def _relative(root: Path, path: Path) -> str:
        return path.relative_to(root).as_posix()

    def discover(self, scope: str, path: str = ".") -> dict[str, Any]:
        root = self.root(scope, path)
        files = self._files(root)
        manifests = [
            name for name in (
                "pyproject.toml", "requirements.txt", "package.json", "pnpm-lock.yaml",
                "package-lock.json", "yarn.lock", "Cargo.toml", "go.mod", "pom.xml",
                "build.gradle", "build.gradle.kts", "composer.json",
            )
            if (root / name).is_file()
        ]
        language_counts: dict[str, int] = {}
        for item in files:
            language = LANGUAGE_BY_EXTENSION.get(item.suffix.casefold())
            if language:
                language_counts[language] = language_counts.get(language, 0) + 1
        instruction_files = [name for name in INSTRUCTION_FILES if (root / name).is_file()]
        return {
            "scope": scope.casefold(),
            "path": path,
            "name": root.name,
            "git_repository": (root / ".git").exists(),
            "manifests": manifests,
            "languages": dict(sorted(language_counts.items(), key=lambda item: (-item[1], item[0]))),
            "indexed_files": len(files),
            "truncated": len(files) >= MAX_PROJECT_FILES,
            "instruction_files": instruction_files,
            "ignore_rules": {
                "gitignore": (root / ".gitignore").is_file(),
                "default_ignored_directories": sorted(DEFAULT_IGNORES),
            },
        }

    def repo_map(self, scope: str, path: str = ".", maximum_files: int = 400) -> dict[str, Any]:
        root = self.root(scope, path)
        limit = max(20, min(int(maximum_files), 1_000))
        files = self._files(root)
        entries: list[dict[str, Any]] = []
        directories: dict[str, int] = {}
        for item in files[:limit]:
            relative = self._relative(root, item)
            parent = str(Path(relative).parent).replace("\\", "/")
            parent = "." if parent == "." else parent
            directories[parent] = directories.get(parent, 0) + 1
            entries.append({
                "path": relative,
                "size_bytes": item.stat().st_size,
                "language": LANGUAGE_BY_EXTENSION.get(item.suffix.casefold()),
            })
        return {
            "scope": scope.casefold(),
            "path": path,
            "directories": [
                {"path": key, "file_count": value}
                for key, value in sorted(directories.items())
            ],
            "files": entries,
            "total_indexed_files": len(files),
            "returned_files": len(entries),
            "truncated": len(files) > len(entries),
        }

    def dependencies(self, scope: str, path: str = ".") -> dict[str, Any]:
        root = self.root(scope, path)
        sources: dict[str, list[str]] = {}

        package = root / "package.json"
        if package.is_file():
            try:
                payload = json.loads(package.read_text(encoding="utf-8"))
                values: list[str] = []
                for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                    section = payload.get(field, {})
                    if isinstance(section, dict):
                        values.extend(f"{name}@{version}" for name, version in section.items())
                sources["package.json"] = sorted(set(values), key=str.casefold)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                sources["package.json"] = []

        pyproject = root / "pyproject.toml"
        if pyproject.is_file():
            try:
                payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                values = []
                project = payload.get("project", {})
                if isinstance(project, dict) and isinstance(project.get("dependencies"), list):
                    values.extend(str(item) for item in project["dependencies"])
                poetry = payload.get("tool", {}).get("poetry", {}) if isinstance(payload.get("tool", {}), dict) else {}
                if isinstance(poetry, dict) and isinstance(poetry.get("dependencies"), dict):
                    values.extend(str(name) for name in poetry["dependencies"] if str(name).casefold() != "python")
                sources["pyproject.toml"] = sorted(set(values), key=str.casefold)
            except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
                sources["pyproject.toml"] = []

        requirements = root / "requirements.txt"
        if requirements.is_file():
            try:
                values = [
                    line.strip() for line in requirements.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.lstrip().startswith(("#", "-r", "--"))
                ]
                sources["requirements.txt"] = values
            except (OSError, UnicodeDecodeError):
                sources["requirements.txt"] = []

        cargo = root / "Cargo.toml"
        if cargo.is_file():
            try:
                payload = tomllib.loads(cargo.read_text(encoding="utf-8"))
                values = []
                for field in ("dependencies", "dev-dependencies", "build-dependencies"):
                    section = payload.get(field, {})
                    if isinstance(section, dict):
                        values.extend(str(name) for name in section)
                sources["Cargo.toml"] = sorted(set(values), key=str.casefold)
            except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
                sources["Cargo.toml"] = []

        return {
            "scope": scope.casefold(),
            "path": path,
            "sources": sources,
            "dependency_count": sum(len(values) for values in sources.values()),
        }

    @staticmethod
    def _python_symbols(text: str, relative: str) -> list[dict[str, Any]]:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []
        results = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                results.append({
                    "name": node.name,
                    "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                    "path": relative,
                    "line": getattr(node, "lineno", None),
                })
        return results

    @staticmethod
    def _script_symbols(text: str, relative: str) -> list[dict[str, Any]]:
        patterns = (
            ("class", re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)", re.M)),
            ("function", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", re.M)),
            ("function", re.compile(r"^\s*(?:export\s+)?(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^\n]*\)\s*=>", re.M)),
            ("type", re.compile(r"^\s*(?:export\s+)?(?:interface|type)\s+([A-Za-z_$][\w$]*)", re.M)),
        )
        results = []
        for kind, pattern in patterns:
            for match in pattern.finditer(text):
                results.append({
                    "name": match.group(1),
                    "kind": kind,
                    "path": relative,
                    "line": text.count("\n", 0, match.start()) + 1,
                })
        return results

    def symbols(self, scope: str, path: str = ".", query: str | None = None, limit: int = 500) -> dict[str, Any]:
        root = self.root(scope, path)
        maximum = max(1, min(int(limit), MAX_SYMBOLS))
        needle = (query or "").strip().casefold()
        results: list[dict[str, Any]] = []
        for item in self._files(root):
            suffix = item.suffix.casefold()
            if suffix not in {".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
                continue
            try:
                text = item.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            relative = self._relative(root, item)
            found = self._python_symbols(text, relative) if suffix in {".py", ".pyi"} else self._script_symbols(text, relative)
            for symbol in found:
                if needle and needle not in symbol["name"].casefold() and needle not in relative.casefold():
                    continue
                results.append(symbol)
                if len(results) >= maximum:
                    break
            if len(results) >= maximum:
                break
        return {
            "scope": scope.casefold(),
            "path": path,
            "query": query,
            "count": len(results),
            "symbols": results,
            "truncated": len(results) >= maximum,
        }

    def search(self, scope: str, path: str, query: str, limit: int = 30) -> dict[str, Any]:
        root = self.root(scope, path)
        terms = [term for term in re.findall(r"[\wÀ-ÿ.-]+", query.casefold()) if len(term) >= 2]
        if not terms:
            raise ProjectIntelligenceError("Search query is required")
        maximum = max(1, min(int(limit), MAX_RESULTS))
        results: list[dict[str, Any]] = []
        for item in self._files(root):
            if item.suffix.casefold() not in TEXT_EXTENSIONS:
                continue
            relative = self._relative(root, item)
            try:
                text = item.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            folded = text.casefold()
            path_folded = relative.casefold()
            score = sum(3 if term in path_folded else 0 for term in terms)
            score += sum(min(folded.count(term), 5) for term in terms)
            if score <= 0:
                continue
            first_line = None
            excerpt = ""
            for number, line in enumerate(text.splitlines(), start=1):
                if any(term in line.casefold() for term in terms):
                    first_line = number
                    excerpt = line.strip()[:500]
                    break
            results.append({
                "path": relative,
                "score": score,
                "line": first_line,
                "excerpt": excerpt,
                "language": LANGUAGE_BY_EXTENSION.get(item.suffix.casefold()),
            })
        results.sort(key=lambda item: (-item["score"], item["path"].casefold()))
        selected = results[:maximum]
        return {
            "scope": scope.casefold(),
            "path": path,
            "query": query,
            "count": len(selected),
            "results": selected,
            "truncated": len(results) > len(selected),
        }

    def working_set(self, scope: str, path: str, task: str, limit: int = 12) -> dict[str, Any]:
        maximum = max(1, min(int(limit), 30))
        search = self.search(scope, path, task, max(maximum * 3, 30))
        symbols = self.symbols(scope, path, query=None, limit=1_000)["symbols"]
        task_terms = {term for term in re.findall(r"[\wÀ-ÿ.-]+", task.casefold()) if len(term) >= 2}
        symbol_paths: dict[str, int] = {}
        for symbol in symbols:
            name = str(symbol["name"]).casefold()
            hits = sum(1 for term in task_terms if term in name)
            if hits:
                symbol_paths[symbol["path"]] = symbol_paths.get(symbol["path"], 0) + hits * 4
        ranked: dict[str, dict[str, Any]] = {}
        for item in search["results"]:
            ranked[item["path"]] = {
                "path": item["path"],
                "score": int(item["score"]) + symbol_paths.get(item["path"], 0),
                "reason": "content/path match" if item["path"] not in symbol_paths else "content + symbol match",
                "excerpt": item.get("excerpt", ""),
            }
        for path_name, score in symbol_paths.items():
            ranked.setdefault(path_name, {"path": path_name, "score": score, "reason": "symbol match", "excerpt": ""})
        selected = sorted(ranked.values(), key=lambda item: (-item["score"], item["path"].casefold()))[:maximum]
        return {
            "scope": scope.casefold(),
            "path": path,
            "task": task,
            "count": len(selected),
            "files": selected,
            "context_strategy": "bounded-working-set",
        }

    def read_instructions(self, scope: str, path: str = ".") -> dict[str, Any]:
        root = self.root(scope, path)
        items = []
        for name in INSTRUCTION_FILES:
            target = root / name
            if target.is_file() and not target.is_symlink():
                try:
                    content = target.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                items.append({"path": name, "content": content[:50_000]})
        return {"scope": scope.casefold(), "path": path, "count": len(items), "items": items}

    def write_instructions(self, scope: str, path: str, content: str, approved: bool) -> dict[str, Any]:
        relative = Path(path, ".rachel", "instructions.md").as_posix() if path not in {"", "."} else ".rachel/instructions.md"
        return self.filesystem.write(scope, relative, content, approved)

    def remember_decision(self, scope: str, path: str, decision: str, approved: bool) -> dict[str, Any]:
        root = self.root(scope, path)
        project_key = f"{scope.casefold()}:{path}:{root.name}"
        content = f"Projeto {project_key} — decisão arquitetural: {' '.join(decision.strip().split())}"
        return self.memory.remember(
            content,
            approved=approved,
            source="project-intelligence",
            category="decision",
            confidence=1.0,
            importance=5,
            metadata={"project_key": project_key, "scope": scope.casefold(), "path": path, "kind": "architecture-decision"},
        )

    def search_decisions(self, scope: str, path: str, query: str, limit: int = 10) -> dict[str, Any]:
        root = self.root(scope, path)
        project_key = f"{scope.casefold()}:{path}:{root.name}"
        items = self.memory.search(f"{project_key} {query}", limit=max(1, min(int(limit), 50)))
        filtered = [
            item for item in items
            if isinstance(item.get("metadata"), dict) and item["metadata"].get("project_key") == project_key
        ]
        return {"project_key": project_key, "query": query, "count": len(filtered), "items": filtered}
