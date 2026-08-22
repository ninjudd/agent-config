from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from projector.cli import main
from projector.core import ProjectStore


PLAN = """---
status: {status}
{extra}---

# {title}

## 1. Outcome

{body}
"""


class RepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.projects = self.root / "docs" / "projects"
        self.projects.mkdir(parents=True)
        (self.projects / "README.md").write_text("# Projects\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def plan(
        self,
        name: str,
        status: str = "later",
        title: str | None = None,
        body: str = "A useful result.",
        extra: str = "",
    ) -> Path:
        path = self.projects / name / "readme.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            PLAN.format(
                status=status,
                title=title or name.rsplit("/", 1)[-1].title(),
                body=body,
                extra=extra,
            ),
            encoding="utf-8",
        )
        return path

    def invoke(self, *arguments: str, cwd: Path | None = None) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        previous = Path.cwd()
        os.chdir(cwd or self.root)
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(list(arguments))
        finally:
            os.chdir(previous)
        return code, stdout.getvalue(), stderr.getvalue()


class DiscoveryTests(RepositoryTestCase):
    def test_list_discovers_top_level_and_nested_projects_from_a_subdirectory(self) -> None:
        self.plan("payments", "now", "Payments")
        self.plan("payments/invoices", "next", "Invoices")
        notes = self.projects / "payments" / "notes"
        notes.mkdir()
        (notes / "design.md").write_text("No project sentinel.\n", encoding="utf-8")

        code, stdout, stderr = self.invoke(
            "list", "--json", cwd=self.projects / "payments" / "notes"
        )

        self.assertEqual(0, code, stderr)
        payload = json.loads(stdout)
        self.assertEqual(1, payload["schema_version"])
        self.assertEqual(
            ["payments", "payments/invoices"],
            [project["name"] for project in payload["projects"]],
        )

    def test_status_filter_and_human_groups_are_queries_only(self) -> None:
        self.plan("alpha", "now", "Alpha")
        self.plan("beta", "later", "Beta")

        code, stdout, _ = self.invoke("list", "--status", "now")

        self.assertEqual(0, code)
        self.assertIn("now:", stdout)
        self.assertIn("alpha", stdout)
        self.assertNotIn("beta", stdout)
        self.assertFalse((self.projects / "now.md").exists())

    def test_show_returns_frontmatter_and_content(self) -> None:
        path = self.plan("alpha", "next", "Alpha")
        code, stdout, _ = self.invoke("show", "alpha", "--json")
        payload = json.loads(stdout)

        self.assertEqual(0, code)
        self.assertEqual("next", payload["project"]["status"])
        self.assertEqual(path.relative_to(self.root).as_posix(), payload["project"]["path"])
        self.assertIn("status: next", payload["project"]["content"])

    def test_search_reports_the_nearest_containing_project(self) -> None:
        self.plan("parent", "now", body="Parent only")
        self.plan("parent/child", "next", body="Needle in child")
        design = self.projects / "parent" / "child" / "design.md"
        design.write_text("Another needle.\n", encoding="utf-8")

        code, stdout, _ = self.invoke("search", "needle", "--json")
        payload = json.loads(stdout)

        self.assertEqual(0, code)
        self.assertEqual({"parent/child"}, {match["project"] for match in payload["matches"]})
        self.assertEqual(2, len(payload["matches"]))

    def test_root_and_projects_dir_overrides_work(self) -> None:
        alternate = self.root / "plans"
        alternate.mkdir()
        (alternate / "README.md").write_text("# Plans\n", encoding="utf-8")
        path = alternate / "alpha" / "readme.md"
        path.parent.mkdir()
        path.write_text(PLAN.format(status="later", extra="", title="Alpha", body="Done"))

        code, stdout, _ = self.invoke(
            "--root", str(self.root), "--projects-dir", "plans", "list", "--json"
        )

        self.assertEqual(0, code)
        self.assertEqual("alpha", json.loads(stdout)["projects"][0]["name"])


class MutationTests(RepositoryTestCase):
    def test_create_supports_nested_projects_without_moving_the_parent(self) -> None:
        parent = self.plan("payments", "now")

        code, stdout, stderr = self.invoke(
            "create", "invoices", "--parent", "payments", "--status", "next", "--no-edit"
        )

        self.assertEqual(0, code, stderr)
        self.assertEqual("docs/projects/payments/invoices/readme.md\n", stdout)
        self.assertTrue(parent.exists())
        self.assertIn(
            "status: next",
            (self.projects / "payments" / "invoices" / "readme.md").read_text(),
        )

    def test_create_refuses_invalid_or_existing_names(self) -> None:
        self.plan("alpha")
        code, _, stderr = self.invoke("create", "alpha", "--no-edit")
        self.assertEqual(65, code)
        self.assertIn("already exists", stderr)

        code, _, stderr = self.invoke("create", "Not Valid", "--no-edit")
        self.assertEqual(65, code)
        self.assertIn("lowercase", stderr)

    def test_status_changes_only_the_status_scalar(self) -> None:
        path = self.plan(
            "alpha",
            "later",
            extra="owner: team\ncustom: keep-me\n",
            body="Uncommitted body edit.\n",
        )
        before = path.read_text()

        code, stdout, stderr = self.invoke("status", "alpha", "now", "--json")

        self.assertEqual(0, code, stderr)
        self.assertEqual("updated", json.loads(stdout)["action"])
        self.assertEqual(before.replace("status: later", "status: now"), path.read_text())

    def test_done_changes_status_and_reminds_about_the_outcome(self) -> None:
        path = self.plan("alpha", "now")
        code, _, stderr = self.invoke("done", "alpha")
        self.assertEqual(0, code)
        self.assertIn("status: done", path.read_text())
        self.assertIn("shipped", stderr)

    def test_status_reports_when_no_file_changed(self) -> None:
        path = self.plan("alpha", "now")
        before = path.stat().st_mtime_ns

        code, stdout, stderr = self.invoke("status", "alpha", "now", "--json")

        self.assertEqual(0, code, stderr)
        self.assertEqual("unchanged", json.loads(stdout)["action"])
        self.assertEqual(before, path.stat().st_mtime_ns)

    def test_edit_refuses_a_noninteractive_session(self) -> None:
        self.plan("alpha")
        with mock.patch("sys.stdin.isatty", return_value=False):
            code, _, stderr = self.invoke("edit", "alpha")
        self.assertEqual(69, code)
        self.assertIn("interactive terminal", stderr)

    def test_init_adopts_an_empty_repository_and_refuses_existing_content(self) -> None:
        self.temporary.cleanup()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

        code, stdout, stderr = self.invoke("init")
        self.assertEqual(0, code, stderr)
        self.assertEqual("docs/projects/README.md\n", stdout)
        self.assertIn("lowercase `readme.md`", (self.root / stdout.strip()).read_text())

        code, _, stderr = self.invoke("init")
        self.assertEqual(65, code)
        self.assertIn("already exists", stderr)


class ValidationTests(RepositoryTestCase):
    def test_check_accepts_a_valid_tree_and_local_links(self) -> None:
        self.plan("alpha", body="See [design](design.md) and [child](child/).")
        (self.projects / "alpha" / "design.md").write_text("# Design\n")
        self.plan("alpha/child")
        (self.root / "docs" / "architecture.md").write_text("# Architecture\n")
        with (self.projects / "alpha" / "readme.md").open("a") as plan:
            plan.write("\nSee [architecture](../../architecture.md).\n")

        code, stdout, stderr = self.invoke("check")

        self.assertEqual(0, code, stderr)
        self.assertEqual("Project plans are valid.\n", stdout)

    def test_check_reports_every_invalid_plan(self) -> None:
        self.plan("bad-status", "waiting")
        malformed = self.projects / "malformed" / "readme.md"
        malformed.parent.mkdir()
        malformed.write_text("# Missing frontmatter\n")

        code, stdout, _ = self.invoke("check", "--json")
        payload = json.loads(stdout)

        self.assertEqual(65, code)
        self.assertFalse(payload["valid"])
        invalid = [issue for issue in payload["issues"] if issue["code"] == "invalid-project"]
        self.assertEqual(2, len(invalid))

    def test_check_reports_wrong_case_missing_plans_and_broken_links(self) -> None:
        uppercase = self.projects / "uppercase" / "README.md"
        uppercase.parent.mkdir()
        uppercase.write_text(PLAN.format(status="later", extra="", title="Upper", body="Done"))
        self.plan("linked", body="See [missing](missing.md).")

        code, stdout, _ = self.invoke("check", "--json")
        issues = json.loads(stdout)["issues"]
        codes = {issue["code"] for issue in issues}

        self.assertEqual(65, code)
        self.assertIn("wrong-entry-case", codes)
        self.assertIn("missing-plan", codes)
        self.assertIn("broken-project-link", codes)

    def test_check_uses_the_casing_recorded_by_git(self) -> None:
        uppercase = self.projects / "uppercase" / "README.md"
        uppercase.parent.mkdir()
        uppercase.write_text(PLAN.format(status="later", extra="", title="Upper", body="Done"))
        subprocess.run(
            ["git", "-C", str(self.root), "add", "docs/projects/uppercase/README.md"],
            check=True,
        )

        code, stdout, _ = self.invoke("check", "--json")
        issues = json.loads(stdout)["issues"]

        self.assertEqual(65, code)
        self.assertTrue(
            any(
                issue["code"] == "wrong-entry-case"
                and issue["path"] == "docs/projects/uppercase/README.md"
                for issue in issues
            )
        )

    def test_check_reports_malformed_markdown_links(self) -> None:
        self.plan("alpha", body="Broken [link](design.md")
        code, stdout, _ = self.invoke("check", "--json")
        codes = {issue["code"] for issue in json.loads(stdout)["issues"]}
        self.assertEqual(65, code)
        self.assertIn("malformed-project-link", codes)


class StoreTests(RepositoryTestCase):
    def test_store_uses_git_root_from_deep_subdirectory(self) -> None:
        self.plan("alpha")
        deep = self.projects / "alpha" / "notes" / "deep"
        deep.mkdir(parents=True)
        store = ProjectStore(deep)
        self.assertEqual(self.root.resolve(), store.root)
        self.assertEqual("alpha", store.resolve("alpha").name)


if __name__ == "__main__":
    unittest.main()
