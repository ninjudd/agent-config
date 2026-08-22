from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.user_root = Path(self.temporary.name)
        self.claude = self.user_root / "claude"
        self.codex = self.user_root / "codex"
        self.fake_bin = self.user_root / "bin"
        self.log = self.user_root / "commands.log"
        self.fake_bin.mkdir()
        for command, executable in (
            ("pipx", "pipx"),
            ("claude", "host-a"),
            ("codex", "host-b"),
        ):
            path = self.fake_bin / executable
            path.write_text(
                "#!/bin/sh\n"
                f"printf '%s %s\\n' '{command}' \"$*\" >> \"$PROJECTOR_TEST_LOG\"\n"
                "exit 0\n"
            )
            path.chmod(0o755)
        self.environment = {
            **os.environ,
            "PATH": f"{self.fake_bin}:{os.environ['PATH']}",
            "HOME": str(self.user_root),
            "PROJECTOR_USER_ROOT": str(self.user_root),
            "PROJECTOR_CLAUDE_DIR": str(self.claude),
            "PROJECTOR_CODEX_DIR": str(self.codex),
            "PROJECTOR_TEST_LOG": str(self.log),
            "PROJECTOR_CLAUDE_COMMAND": str(self.fake_bin / "host-a"),
            "PROJECTOR_CODEX_COMMAND": str(self.fake_bin / "host-b"),
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def install(self, target: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(ROOT / "install.sh"), target],
            cwd=ROOT,
            env=self.environment,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_host_installs_remove_only_exact_legacy_links(self) -> None:
        self.claude.mkdir()
        self.codex.mkdir()
        (self.claude / "skills").symlink_to(ROOT / "skills")
        (self.codex / "skills").symlink_to(ROOT / "skills")
        (self.user_root / "CLAUDE.md").symlink_to(ROOT / "AGENTS.md")
        (self.codex / "AGENTS.md").symlink_to(ROOT / "AGENTS.md")
        settings = self.claude / "settings.json"
        settings.write_text('{"user": true}\n')
        unrelated = self.codex / "keep"
        unrelated.symlink_to(self.user_root / "somewhere-else")

        claude = self.install("claude")
        codex = self.install("codex")

        self.assertEqual(0, claude.returncode, claude.stderr)
        self.assertEqual(0, codex.returncode, codex.stderr)
        self.assertFalse((self.claude / "skills").exists())
        self.assertFalse((self.codex / "skills").exists())
        self.assertFalse((self.user_root / "CLAUDE.md").exists())
        self.assertFalse((self.codex / "AGENTS.md").exists())
        self.assertEqual('{"user": true}\n', settings.read_text())
        self.assertTrue(unrelated.is_symlink())
        log = self.log.read_text()
        self.assertIn(f"claude plugin marketplace add {ROOT} --scope user", log)
        self.assertIn("claude plugin install projector@projector --scope user", log)
        self.assertIn(f"codex plugin marketplace add {ROOT}", log)
        self.assertIn("codex plugin add projector@projector", log)

    def test_all_skips_one_missing_host_and_installs_the_other(self) -> None:
        self.environment["PROJECTOR_CLAUDE_COMMAND"] = "missing-claude"

        result = self.install("all")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("skipped", result.stdout)
        self.assertIn("codex plugin add projector@projector", self.log.read_text())

    def test_all_fails_when_both_hosts_are_missing(self) -> None:
        self.environment["PROJECTOR_CLAUDE_COMMAND"] = "missing-claude"
        self.environment["PROJECTOR_CODEX_COMMAND"] = "missing-codex"

        result = self.install("all")

        self.assertEqual(69, result.returncode)
        self.assertIn("neither Claude Code nor Codex", result.stderr)

    def test_cli_install_uses_an_isolated_pipx_application(self) -> None:
        result = self.install("cli")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(f"pipx install --force {ROOT}\n", self.log.read_text())

    def test_unknown_target_is_command_misuse(self) -> None:
        result = self.install("unknown")
        self.assertEqual(64, result.returncode)
        self.assertIn("usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
