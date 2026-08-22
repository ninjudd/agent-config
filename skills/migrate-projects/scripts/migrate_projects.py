#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlsplit


LEGACY_STATUSES = {
    "Draft",
    "Active",
    "Blocked",
    "Stalled",
    "Shipped",
    "Superseded",
    "Abandoned",
    "Reference",
}
NEW_STATUSES = {"now", "next", "later", "done"}
TERMINAL = {"Shipped", "Superseded", "Abandoned"}
LIST_FILES = {"now": "now.md", "next": "next.md", "later": "later.md"}
PRIMARY_LINK = re.compile(r"^[ \t]*-[ \t]+\[[^\]]*\]\(([^)]+)\)", re.MULTILINE)
MARKDOWN_LINK = re.compile(r"(?<!!)(\[[^\]]*\]\()([^)]+)(\))", re.DOTALL)
STATUS = re.compile(r"^(status:[ \t]*)([^#\r\n]*?)([ \t]*(?:#.*)?)$", re.MULTILINE)


@dataclass
class Entry:
    name: str
    source: str
    destination: str
    old_status: Optional[str]
    new_status: Optional[str]
    membership: Optional[str]
    kind: str


@dataclass
class Report:
    entries: list[Entry]
    removals: list[str]
    errors: list[str]
    rewrites: list[dict[str, object]]

    def public(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "entries": [asdict(entry) for entry in self.entries],
            "removals": self.removals,
            "errors": self.errors,
            "rewrites": self.rewrites,
        }


def git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=check,
        capture_output=True,
    )


def exact_files(directory: Path, filename: str) -> list[Path]:
    found: list[Path] = []
    if not directory.exists():
        return found
    for current, _, files in os.walk(directory):
        if filename in files:
            found.append(Path(current) / filename)
    return sorted(found)


def read_status(path: Path) -> Optional[str]:
    match = STATUS.search(path.read_text(encoding="utf-8"))
    return match.group(2).strip().strip("\"'") if match else None


def list_memberships(projects: Path) -> tuple[dict[str, set[str]], list[str]]:
    memberships: dict[str, set[str]] = {}
    errors: list[str] = []
    for status, filename in LIST_FILES.items():
        path = projects / filename
        if not path.exists():
            continue
        for raw in PRIMARY_LINK.findall(path.read_text(encoding="utf-8")):
            target = raw.strip().split(maxsplit=1)[0].strip("<>\"'")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            normalized = unquote(parsed.path).lstrip("./")
            if not normalized.startswith("all/"):
                continue
            name = normalized[4:].rstrip("/")
            if name.endswith(("/README.md", "/overview.md")):
                name = name.rsplit("/", 1)[0]
            elif name.endswith(".md"):
                name = name[:-3]
            memberships.setdefault(name, set()).add(status)
    return memberships, errors


def inventory(root: Path) -> Report:
    projects = root / "docs" / "projects"
    all_dir = projects / "all"
    memberships, errors = list_memberships(projects)
    entries: list[Entry] = []
    sources: dict[str, Path] = {}

    if not all_dir.is_dir():
        errors.append(f"missing legacy directory: {all_dir.relative_to(root)}")
        return Report(entries, [], errors, [])

    for path in all_dir.rglob("*"):
        if path.is_symlink():
            errors.append(f"{path.relative_to(root)}: symlinks are not allowed in all/")

    for path in sorted(all_dir.glob("*.md")):
        sources[path.stem] = path
    for filename in ("README.md", "overview.md"):
        for path in exact_files(all_dir, filename):
            name = path.parent.relative_to(all_dir).as_posix()
            if name in sources:
                errors.append(f"{name}: multiple legacy project entry points exist")
            else:
                sources[name] = path

    for child in all_dir.iterdir():
        if child.is_dir() and child.name not in sources:
            errors.append(f"{child.name}: folder has no top-level README.md or overview.md")
        elif child.is_file() and child.suffix != ".md":
            errors.append(f"{child.name}: unrecognized file at the root of all/")

    for name, source in sorted(sources.items()):
        if source.parent != all_dir and "/" in name:
            top = name.split("/", 1)[0]
            if top not in sources:
                errors.append(f"{name}: nested project has no top-level project entry point")

    for listed in sorted(memberships):
        if listed not in sources:
            errors.append(f"{listed}: list target has no legacy plan")

    top_folder_references: set[str] = set()
    for name, source in sorted(sources.items()):
        old_status = read_status(source)
        values = memberships.get(name, set())
        membership = next(iter(values)) if len(values) == 1 else None
        if len(values) > 1 and old_status not in TERMINAL | {"Reference"}:
            errors.append(
                f"{name}: appears in multiple lists: {', '.join(sorted(values))}"
            )
        kind = "project"
        new_status: Optional[str]

        if old_status is not None and old_status not in LEGACY_STATUSES | NEW_STATUSES:
            new_status = None
            errors.append(f"{name}: unknown lifecycle status {old_status!r}")
        elif old_status in TERMINAL:
            new_status = "done"
        elif old_status == "Reference":
            kind = "reference"
            new_status = None
        elif membership:
            new_status = membership
        elif old_status in ("Active", "Blocked"):
            new_status = "now"
        elif old_status in ("Draft", "Stalled"):
            new_status = "later"
        elif old_status in NEW_STATUSES:
            new_status = old_status
        elif old_status is None:
            new_status = None
            errors.append(f"{name}: has neither status nor list membership")

        relative_source = source.relative_to(root).as_posix()
        folder_shaped = source.parent != all_dir
        if kind == "reference":
            top = name.split("/", 1)[0]
            if "/" in name:
                errors.append(f"{name}: nested Reference requires manual placement")
            elif folder_shaped:
                destination = f"docs/{name}/README.md"
                top_folder_references.add(top)
            else:
                destination = f"docs/{name}.md"
        else:
            destination = f"docs/projects/{name}/readme.md"

        destination_path = root / destination
        source_root = source.parent if folder_shaped else source
        destination_root = (
            destination_path.parent
            if folder_shaped or kind == "project"
            else destination_path
        )
        if destination_root.exists() and destination_root.resolve() != source_root.resolve():
            errors.append(f"{name}: destination already exists: {destination}")
        entries.append(
            Entry(name, relative_source, destination, old_status, new_status, membership, kind)
        )

    for reference in top_folder_references:
        nested = [entry.name for entry in entries if entry.name.startswith(f"{reference}/")]
        if nested:
            errors.append(
                f"{reference}: Reference folder also contains project entries: {', '.join(nested)}"
            )

    removals = [
        (projects / filename).relative_to(root).as_posix()
        for filename in ("README.md", *LIST_FILES.values())
        if (projects / filename).exists()
    ]
    report = Report(entries, removals, sorted(set(errors)), [])
    report.rewrites = describe_rewrites(root, report)
    return report


def update_status(path: Path, old_status: Optional[str], new_status: str) -> None:
    text = path.read_text(encoding="utf-8")
    match = STATUS.search(text)
    if match:
        current = match.group(2).strip().strip("\"'")
        if old_status is not None and current != old_status:
            raise RuntimeError(f"{path}: status changed after the dry run")
        text = text[: match.start(2)] + new_status + text[match.end(2) :]
    elif text.startswith("---\n"):
        text = text.replace("---\n", f"---\nstatus: {new_status}\n", 1)
    else:
        text = f"---\nstatus: {new_status}\n---\n\n{text}"

    if old_status in TERMINAL and "**Outcome:**" not in text:
        closing = text.find("\n---", 4)
        insertion = closing + 4 if closing >= 0 else 0
        text = text[:insertion] + f"\n\n**Outcome:** {old_status}." + text[insertion:]
    path.write_text(text, encoding="utf-8")


def remove_reference_status(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    match = STATUS.search(text)
    if match:
        start = match.start()
        end = match.end()
        if end < len(text) and text[end] == "\n":
            end += 1
        text = text[:start] + text[end:]
    path.write_text(text, encoding="utf-8")


def move_case_safely(root: Path, source: Path, destination: Path) -> None:
    if source == destination:
        return
    temporary = source.with_name(f".{source.name}.projector-move")
    git(root, "mv", str(source.relative_to(root)), str(temporary.relative_to(root)))
    git(root, "mv", str(temporary.relative_to(root)), str(destination.relative_to(root)))


def _replace_path(data: bytes, old: bytes, new: bytes) -> tuple[bytes, int]:
    suffix = rb"" if old.endswith(b"/") else rb"(?![A-Za-z0-9_-])"
    pattern = re.compile(rb"(?<![A-Za-z0-9_-])" + re.escape(old) + suffix)
    return pattern.subn(lambda _: new, data)


def reference_replacements(report: Report) -> dict[bytes, bytes]:
    replacements: dict[bytes, bytes] = {}
    for entry in report.entries:
        replacements[entry.source.encode()] = entry.destination.encode()
        source_name = Path(entry.source).name
        if source_name in ("README.md", "overview.md"):
            top = entry.name.split("/", 1)[0]
            top_entry = next((item for item in report.entries if item.name == top), None)
            if top_entry is not None:
                replacements[f"docs/projects/all/{top}/".encode()] = (
                    f"docs/{top}/"
                    if top_entry.kind == "reference"
                    else f"docs/projects/{top}/"
                ).encode()
                replacements[f"all/{top}/".encode()] = (
                    f"../{top}/" if top_entry.kind == "reference" else f"{top}/"
                ).encode()
            old = f"all/{entry.name}/{source_name}".encode()
            new = (
                f"../{entry.name}/README.md"
                if entry.kind == "reference"
                else f"{entry.name}/readme.md"
            ).encode()
        else:
            old = f"all/{entry.name}.md".encode()
            new = (
                f"../{entry.name}.md"
                if entry.kind == "reference"
                else f"{entry.name}/readme.md"
            ).encode()
        replacements[old] = new
    return replacements


def describe_rewrites(root: Path, report: Report) -> list[dict[str, object]]:
    tracked = git(root, "ls-files", "-z").stdout.split(b"\0")
    rewrites: list[dict[str, object]] = []
    for old, new in sorted(reference_replacements(report).items()):
        touched = 0
        for raw_path in tracked:
            if not raw_path:
                continue
            path = root / raw_path.decode("utf-8", errors="surrogateescape")
            if not path.is_file() or path.is_symlink():
                continue
            _, count = _replace_path(path.read_bytes(), old, new)
            touched += int(count > 0)
        if touched:
            rewrites.append(
                {
                    "old": old.decode("utf-8"),
                    "new": new.decode("utf-8"),
                    "files": touched,
                }
            )
    rewrites.append(
        {
            "old": "relative Markdown links from moved plans",
            "new": "paths relative to each permanent destination",
            "files": "resolved during apply",
        }
    )
    return rewrites


def rewrite_references(root: Path, replacements: dict[bytes, bytes]) -> None:
    tracked = git(root, "ls-files", "-z").stdout.split(b"\0")
    ordered = sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True)
    for raw_path in tracked:
        if not raw_path:
            continue
        path = root / raw_path.decode("utf-8", errors="surrogateescape")
        if not path.is_file() or path.is_symlink():
            continue
        before = path.read_bytes()
        after = before
        for old, new in ordered:
            after, _ = _replace_path(after, old, new)
        if after != before:
            path.write_bytes(after)


def repair_markdown_links(root: Path, report: Report) -> None:
    projects = {
        entry.name: root / entry.destination
        for entry in report.entries
        if entry.kind == "project"
    }
    references = {
        entry.name: (root / entry.destination).parent
        for entry in report.entries
        if entry.kind == "reference" and entry.destination.endswith("/README.md")
    }
    convention = root / "docs" / "projects" / "README.md"

    def exact_name_exists(candidate: Path) -> bool:
        try:
            return candidate.name in {child.name for child in candidate.parent.iterdir()}
        except OSError:
            return False

    def replacement(path: Path, match: re.Match[str]) -> str:
        raw = match.group(2)
        token = raw.strip().split(maxsplit=1)[0].strip("<>\"'")
        parsed = urlsplit(token)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group(0)
        current = (path.parent / unquote(parsed.path)).resolve()
        if exact_name_exists(current):
            return match.group(0)

        target: Optional[Path] = None
        target_path = Path(unquote(parsed.path))
        if target_path.name in ("README.md", "overview.md"):
            lowercase_entry = current.with_name("readme.md")
            if exact_name_exists(lowercase_entry):
                target = lowercase_entry
        if target is None and target_path.name in LIST_FILES.values():
            target = convention
        elif target is None:
            stem = target_path.stem
            if stem in projects:
                target = projects[stem]
            elif target_path.parts and target_path.parts[0] in references:
                target = references[target_path.parts[0]].joinpath(*target_path.parts[1:])
            else:
                candidates = [
                    candidate
                    for candidate in (root / "docs").rglob(target_path.name)
                    if candidate.is_file()
                ]
                if len(candidates) == 1:
                    target = candidates[0]
        if target is None or not target.exists():
            return match.group(0)

        relative = Path(os.path.relpath(target, path.parent)).as_posix()
        if parsed.query:
            relative += f"?{parsed.query}"
        if parsed.fragment:
            relative += f"#{parsed.fragment}"
        leading = raw[: len(raw) - len(raw.lstrip())]
        trailing = raw[len(raw.rstrip()) :]
        stripped = raw.strip()
        first = stripped.split(maxsplit=1)[0]
        title = stripped[len(first) :]
        return (
            f"{match.group(1)}{leading}{relative}{title}{trailing}{match.group(3)}"
        )

    for path in sorted((root / "docs").rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = MARKDOWN_LINK.sub(lambda match: replacement(path, match), text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def projector_command() -> list[str]:
    executable = shutil.which("projector")
    if executable:
        return [executable]
    if importlib.util.find_spec("projector") is not None:
        return [sys.executable, "-m", "projector"]
    raise RuntimeError("install the projector CLI before applying migration")


def apply(root: Path, report: Report) -> None:
    if report.errors:
        raise RuntimeError("refusing to apply an ambiguous migration")
    command = projector_command()
    probe = subprocess.run([*command, "--help"], text=True, capture_output=True)
    if probe.returncode:
        raise RuntimeError("projector CLI is unavailable or failed its preflight")
    dirty = git(root, "status", "--porcelain").stdout
    if dirty:
        raise RuntimeError("repository has uncommitted changes")

    try:
        _apply_changes(root, report, command)
    except BaseException:
        git(root, "reset", "--hard", "HEAD", check=False)
        print("migrate-projects: rolled back to the clean starting commit", file=sys.stderr)
        raise


def _apply_changes(root: Path, report: Report, command: list[str]) -> None:

    projects = root / "docs" / "projects"
    entries = {entry.name: entry for entry in report.entries}
    replacements = reference_replacements(report)

    moved_folders: set[str] = set()
    for entry in sorted(report.entries, key=lambda item: (item.name.count("/"), item.name)):
        source = root / entry.source
        if source.parent != projects / "all":
            top = entry.name.split("/", 1)[0]
            if top not in moved_folders:
                source_folder = projects / "all" / top
                if entries[top].kind == "reference":
                    destination_folder = root / "docs" / top
                else:
                    destination_folder = projects / top
                destination_folder.parent.mkdir(parents=True, exist_ok=True)
                git(
                    root,
                    "mv",
                    str(source_folder.relative_to(root)),
                    str(destination_folder.relative_to(root)),
                )
                moved_folders.add(top)
            old_prefix = f"docs/projects/all/{top}/".encode()
            if entries[top].kind == "reference":
                new_prefix = f"docs/{top}/".encode()
            else:
                new_prefix = f"docs/projects/{top}/".encode()
            replacements[old_prefix] = new_prefix
            replacements[f"all/{top}/".encode()] = (
                f"../{top}/".encode() if entries[top].kind == "reference" else f"{top}/".encode()
            )
            replacements[entry.source.encode()] = entry.destination.encode()
            old_relative = f"all/{entry.name}/{source.name}".encode()
            if entry.kind == "reference":
                replacements[old_relative] = f"../{entry.name}/README.md".encode()
            else:
                replacements[old_relative] = f"{entry.name}/readme.md".encode()
        elif entry.kind == "reference":
            destination = root / entry.destination
            destination.parent.mkdir(parents=True, exist_ok=True)
            git(root, "mv", entry.source, entry.destination)
            replacements[entry.source.encode()] = entry.destination.encode()
            replacements[f"all/{entry.name}.md".encode()] = f"../{entry.name}.md".encode()
        else:
            destination = root / entry.destination
            destination.parent.mkdir(parents=True, exist_ok=True)
            git(root, "mv", entry.source, entry.destination)
            replacements[entry.source.encode()] = entry.destination.encode()
            replacements[f"all/{entry.name}.md".encode()] = f"{entry.name}/readme.md".encode()

    for entry in report.entries:
        destination = root / entry.destination
        source_name = Path(entry.source).name
        if source_name in ("README.md", "overview.md"):
            legacy = destination.with_name(source_name)
            if legacy != destination and legacy.exists():
                move_case_safely(root, legacy, destination)
        if entry.kind == "reference":
            remove_reference_status(destination)
        else:
            assert entry.new_status is not None
            update_status(destination, entry.old_status, entry.new_status)

    for path in report.removals:
        if (root / path).exists():
            git(root, "rm", path)
    (projects / "all").rmdir()
    initialized = subprocess.run(
        [*command, "--root", str(root), "init"], text=True, capture_output=True
    )
    if initialized.returncode:
        raise RuntimeError(
            f"projector init failed:\n{initialized.stderr or initialized.stdout}"
        )
    git(root, "add", "docs/projects/README.md")

    rewrite_references(root, replacements)
    repair_markdown_links(root, report)
    check = subprocess.run(
        [*command, "--root", str(root), "check"],
        text=True,
        capture_output=True,
    )
    if check.returncode:
        raise RuntimeError(f"projector check failed:\n{check.stderr or check.stdout}")


def render(report: Report) -> str:
    lines = []
    for entry in report.entries:
        status = entry.new_status or "reference"
        lines.append(f"{entry.kind:<9} {entry.name:<32} {status:<9} {entry.destination}")
    for removal in report.removals:
        lines.append(f"remove    {removal}")
    for rewrite in report.rewrites:
        lines.append(
            f"rewrite   {rewrite['old']} -> {rewrite['new']} ({rewrite['files']} files)"
        )
    for error in report.errors:
        lines.append(f"error     {error}")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy Projector plans")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    arguments = parser.parse_args(argv)
    try:
        root = Path(
            git(arguments.root.resolve(), "rev-parse", "--show-toplevel").stdout.decode().strip()
        )
        report = inventory(root)
        if arguments.json_output:
            print(json.dumps(report.public(), indent=2, sort_keys=True))
        else:
            print(render(report))
        if report.errors:
            return 65
        if arguments.apply:
            apply(root, report)
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"migrate-projects: {error}", file=sys.stderr)
        return 65


if __name__ == "__main__":
    raise SystemExit(main())
