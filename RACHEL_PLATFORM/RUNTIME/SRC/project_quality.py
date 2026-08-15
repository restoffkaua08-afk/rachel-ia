from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from project_workspace import ProjectWorkspace, WorkspaceError


class QualityError(RuntimeError):
    pass


class HtmlEvidenceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._inside_title = False
        self.headings = 0
        self.images = []
        self.links = []
        self.has_lang = False
        self.has_viewport = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "html" and values.get("lang"):
            self.has_lang = True
        if tag == "meta" and values.get("name", "").casefold() == "viewport":
            self.has_viewport = True
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings += 1
        if tag == "img":
            self.images.append({"src": values.get("src", ""), "alt": values.get("alt")})
        if tag == "a":
            self.links.append(values.get("href", ""))
        if tag == "title":
            self._inside_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._inside_title = False

    def handle_data(self, data):
        if self._inside_title:
            self.title += data


class ProjectQuality:
    def __init__(self, workspace=None):
        self.workspace = workspace or ProjectWorkspace()

    @staticmethod
    def _is_local_reference(value: str) -> bool:
        clean = value.strip()
        return bool(clean) and not clean.startswith(("http://", "https://", "//", "#", "mailto:", "tel:", "data:", "javascript:"))

    def review(self, project: str) -> dict[str, Any]:
        inspection = self.workspace.inspect(project)
        project_root = Path(inspection["path"])
        issues = []
        warnings = []
        checks = {
            "has_files": inspection["file_count"] > 0,
            "has_documentation": any(item["path"].casefold() == "readme.md" for item in inspection["files"]),
            "no_empty_files": True,
            "no_placeholders": True,
            "html_has_title": True,
            "html_has_language": True,
            "html_has_viewport": True,
            "images_have_alt": True,
            "local_references_exist": True,
        }
        placeholders = re.compile(r"\b(?:todo|fixme|lorem ipsum|coming soon)\b|\.\.\.", re.I)
        for item in inspection["files"]:
            relative = item["path"]
            path = project_root / relative
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                issues.append({"severity": "error", "code": "non_text_file", "path": relative})
                continue
            if not text.strip():
                checks["no_empty_files"] = False
                issues.append({"severity": "error", "code": "empty_file", "path": relative})
            if placeholders.search(text):
                checks["no_placeholders"] = False
                warnings.append({"severity": "warning", "code": "placeholder", "path": relative})
            if path.suffix.casefold() in {".html", ".htm"}:
                parser = HtmlEvidenceParser()
                parser.feed(text)
                if not parser.title.strip():
                    checks["html_has_title"] = False
                    issues.append({"severity": "error", "code": "missing_title", "path": relative})
                if not parser.has_lang:
                    checks["html_has_language"] = False
                    warnings.append({"severity": "warning", "code": "missing_html_lang", "path": relative})
                if not parser.has_viewport:
                    checks["html_has_viewport"] = False
                    warnings.append({"severity": "warning", "code": "missing_viewport", "path": relative})
                for image in parser.images:
                    if image["alt"] is None:
                        checks["images_have_alt"] = False
                        warnings.append({"severity": "warning", "code": "missing_image_alt", "path": relative, "reference": image["src"]})
                references = [image["src"] for image in parser.images] + parser.links
                for reference in references:
                    if self._is_local_reference(reference):
                        clean = reference.split("?", 1)[0].split("#", 1)[0]
                        target = (path.parent / clean).resolve()
                        try:
                            target.relative_to(project_root.resolve())
                        except ValueError:
                            checks["local_references_exist"] = False
                            issues.append({"severity": "error", "code": "unsafe_reference", "path": relative, "reference": reference})
                            continue
                        if not target.exists():
                            checks["local_references_exist"] = False
                            issues.append({"severity": "error", "code": "broken_reference", "path": relative, "reference": reference})
        passed = sum(1 for value in checks.values() if value)
        score = round(100 * passed / len(checks))
        accepted = not issues and score >= 80
        return {
            "project": project,
            "path": inspection["path"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "accepted": accepted,
            "score": score,
            "checks": checks,
            "issues": issues,
            "warnings": warnings,
            "file_count": inspection["file_count"],
            "files": inspection["files"],
        }

    def report_markdown(self, result: dict[str, Any]) -> str:
        lines = [
            f"# Relatorio de desenvolvimento â€” {result['project']}", "",
            f"- Status: {'APROVADO' if result['accepted'] else 'REPROVADO'}",
            f"- Nota tecnica: {result['score']}/100",
            f"- Arquivos analisados: {result['file_count']}",
            f"- Data UTC: {result['reviewed_at']}", "", "## Verificacoes", "",
        ]
        for name, passed in result["checks"].items():
            lines.append(f"- [{'x' if passed else ' '}] {name}")
        lines.extend(["", "## Problemas", ""])
        if result["issues"]:
            for issue in result["issues"]:
                lines.append(f"- **{issue['code']}** â€” `{issue.get('path', '')}`")
        else:
            lines.append("Nenhum problema bloqueante encontrado.")
        lines.extend(["", "## Alertas", ""])
        if result["warnings"]:
            for warning in result["warnings"]:
                lines.append(f"- **{warning['code']}** â€” `{warning.get('path', '')}`")
        else:
            lines.append("Nenhum alerta encontrado.")
        lines.extend(["", "## Arquivos", ""])
        for item in result["files"]:
            lines.append(f"- `{item['path']}` â€” {item['size_bytes']} bytes â€” `{item['sha256']}`")
        return "\n".join(lines).rstrip() + "\n"

    def write_report(self, project: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber requires approval to write a report.")
        result = self.review(project)
        written = self.workspace.write_files(project, [{"path": "RACHEL_REPORT.md", "content": self.report_markdown(result)}], approved=True)
        return {"state": "completed", "quality": result, "report": "RACHEL_REPORT.md", "operation_id": written["operation_id"]}


def main() -> int:
    parser = argparse.ArgumentParser(prog="project-quality")
    parser.add_argument("--root")
    sub = parser.add_subparsers(dest="command", required=True)
    review = sub.add_parser("review"); review.add_argument("--project", required=True)
    report = sub.add_parser("report"); report.add_argument("--project", required=True); report.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    quality = ProjectQuality(ProjectWorkspace(args.root))
    result = quality.review(args.project) if args.command == "review" else quality.write_report(args.project, args.approved)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("accepted", result.get("quality", {}).get("accepted", False)) else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, PermissionError, WorkspaceError, QualityError) as error:
        print(json.dumps({"state": "rejected", "error": str(error)}, ensure_ascii=False, indent=2))
        raise SystemExit(3)
