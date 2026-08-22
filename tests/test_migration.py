from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "skills"
    / "migrate-projects"
    / "scripts"
    / "migrate_projects.py"
)
SPEC = importlib.util.spec_from_file_location("migrate_projects", SCRIPT)
assert SPEC and SPEC.loader
MIGRATE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MIGRATE
SPEC.loader.exec_module(MIGRATE)


def legacy_plan(status: str | None, title: str) -> str:
    frontmatter = f"---\nstatus: {status}\n---\n\n" if status else ""
    return f"{frontmatter}# {title}\n\nExisting explanation.\n"


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.name", "Projector Test"],
            check=True,
        )
        self.projects = self.root / "docs" / "projects"
        self.all = self.projects / "all"
        self.all.mkdir(parents=True)
        (self.projects / "README.md").write_text("# Legacy projects\n")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def commit_fixture(self) -> None:
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-qm", "Add legacy fixture"],
            check=True,
        )

    def invoke(self, *arguments: str) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = MIGRATE.main(["--root", str(self.root), *arguments])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_dry_run_and_apply_cover_legacy_layouts_and_statuses(self) -> None:
        self.write(
            "docs/projects/now.md",
            "Write plans in [all](all/).\n\n- [Alpha](all/alpha.md)\n",
        )
        self.write("docs/projects/next.md", "- [Folder](all/folder/README.md)\n")
        self.write(
            "docs/projects/later.md",
            "- [No status](all/no-status.md)\n"
            "- **Related idea** — see [Alpha](all/alpha.md).\n",
        )
        self.write("docs/projects/all/alpha.md", legacy_plan("Draft", "Alpha"))
        self.write("docs/projects/all/active.md", legacy_plan("Active", "Active"))
        self.write("docs/projects/all/blocked.md", legacy_plan("Blocked", "Blocked"))
        self.write("docs/projects/all/stalled.md", legacy_plan("Stalled", "Stalled"))
        self.write("docs/projects/all/shipped.md", legacy_plan("Shipped", "Shipped"))
        self.write("docs/projects/all/superseded.md", legacy_plan("Superseded", "Superseded"))
        self.write("docs/projects/all/abandoned.md", legacy_plan("Abandoned", "Abandoned"))
        self.write("docs/projects/all/reference.md", legacy_plan("Reference", "Reference"))
        self.write(
            "docs/projects/all/decisions/overview.md",
            legacy_plan("Reference", "Decisions"),
        )
        self.write("docs/projects/all/decisions/note.md", "# Note\n")
        self.write("docs/projects/all/no-status.md", legacy_plan(None, "No status"))
        self.write("docs/projects/all/folder/README.md", legacy_plan("Draft", "Folder"))
        self.write(
            "docs/projects/all/folder/child/README.md",
            legacy_plan("Stalled", "Child"),
        )
        self.write("docs/projects/all/folder/design.md", "# Design\n")
        self.write(
            "notes.txt",
            "See docs/projects/all/alpha.md and docs/projects/all/folder/design.md.\n",
        )
        (self.root / "binary-notes.md").write_bytes(
            b"before\0docs/projects/all/alpha.md after\n"
        )
        self.commit_fixture()

        code, stdout, stderr = self.invoke("--json")
        report = json.loads(stdout)

        self.assertEqual(0, code, stderr)
        self.assertEqual([], report["errors"])
        mapped = {entry["name"]: entry for entry in report["entries"]}
        self.assertEqual("now", mapped["alpha"]["new_status"])
        self.assertEqual("next", mapped["folder"]["new_status"])
        self.assertEqual("later", mapped["folder/child"]["new_status"])
        self.assertEqual("done", mapped["shipped"]["new_status"])
        self.assertEqual("reference", mapped["reference"]["kind"])

        code, _, stderr = self.invoke("--apply")
        self.assertEqual(0, code, stderr)

        expected = {
            "alpha": "now",
            "active": "now",
            "blocked": "now",
            "stalled": "later",
            "shipped": "done",
            "superseded": "done",
            "abandoned": "done",
            "no-status": "later",
            "folder": "next",
            "folder/child": "later",
        }
        for name, status in expected.items():
            path = self.projects / name / "readme.md"
            self.assertTrue(path.exists(), name)
            self.assertIn(f"status: {status}", path.read_text())
        self.assertTrue((self.projects / "folder" / "design.md").exists())
        self.assertFalse((self.projects / "all").exists())
        self.assertFalse((self.projects / "now.md").exists())
        self.assertIn("lowercase `readme.md`", (self.projects / "README.md").read_text())
        self.assertIn("**Outcome:** Shipped.", (self.projects / "shipped" / "readme.md").read_text())
        reference = self.root / "docs" / "reference.md"
        self.assertTrue(reference.exists())
        self.assertNotIn("status:", reference.read_text())
        decisions = self.root / "docs" / "decisions" / "README.md"
        self.assertTrue(decisions.exists())
        self.assertNotIn("status:", decisions.read_text())
        self.assertTrue((self.root / "docs" / "decisions" / "note.md").exists())
        self.assertIn("docs/projects/alpha/readme.md", (self.root / "notes.txt").read_text())
        self.assertIn("docs/projects/folder/design.md", (self.root / "notes.txt").read_text())
        self.assertIn(
            b"docs/projects/alpha/readme.md", (self.root / "binary-notes.md").read_bytes()
        )

    def test_ambiguous_membership_refuses_to_apply(self) -> None:
        self.write("docs/projects/now.md", "- [Alpha](all/alpha.md)\n")
        self.write("docs/projects/next.md", "- [Alpha](all/alpha.md)\n")
        self.write("docs/projects/all/alpha.md", legacy_plan("Draft", "Alpha"))
        self.commit_fixture()
        before = subprocess.run(
            ["git", "-C", str(self.root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        code, stdout, _ = self.invoke("--apply", "--json")

        self.assertEqual(65, code)
        self.assertIn("multiple lists", " ".join(json.loads(stdout)["errors"]))
        after = subprocess.run(
            ["git", "-C", str(self.root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(before, after)

    def test_missing_classification_is_reported(self) -> None:
        self.write("docs/projects/all/unknown.md", legacy_plan(None, "Unknown"))
        self.commit_fixture()

        code, stdout, _ = self.invoke("--json")

        self.assertEqual(65, code)
        self.assertIn("neither status nor list membership", " ".join(json.loads(stdout)["errors"]))


if __name__ == "__main__":
    unittest.main()
