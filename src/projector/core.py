from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote, urlsplit


STATUSES = ("now", "next", "later", "done")
NAME_PART = re.compile(r"^[a-z0-9][a-z0-9-]*$")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
FRONTMATTER_LINE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*)$")
STATUS_LINE = re.compile(
    r"^(?P<prefix>status:[ \t]*)(?P<value>[^#\r\n]*?)"
    r"(?P<suffix>[ \t]*(?:#.*)?)$",
    re.MULTILINE,
)


class ProjectorError(Exception):
    exit_code = 65


class ProjectNotFound(ProjectorError):
    exit_code = 66


class AmbiguousProject(ProjectorError):
    exit_code = 67


class EnvironmentError(ProjectorError):
    exit_code = 69


@dataclass(frozen=True)
class Project:
    name: str
    title: str
    status: str
    path: Path
    owner: Optional[str] = None

    def public(self, root: Path) -> dict[str, object]:
        value = asdict(self)
        value["path"] = self.path.relative_to(root).as_posix()
        return value


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str


def discover_git_root(start: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise EnvironmentError(f"not inside a Git repository: {start}") from error
    return Path(result.stdout.strip()).resolve()


def valid_name(name: str) -> bool:
    return bool(name) and all(NAME_PART.fullmatch(part) for part in name.split("/"))


def parse_frontmatter(text: str, path: Path) -> tuple[dict[str, str], int]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ProjectorError(f"{path}: missing YAML frontmatter")

    metadata: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        value = line.rstrip("\r\n")
        if value == "---":
            return metadata, index + 1
        if not value or value.lstrip().startswith("#"):
            continue
        match = FRONTMATTER_LINE.fullmatch(value)
        if not match:
            raise ProjectorError(f"{path}:{index + 1}: malformed frontmatter")
        key, raw = match.groups()
        if key in metadata:
            raise ProjectorError(f"{path}:{index + 1}: duplicate {key!r} field")
        metadata[key] = raw.strip().strip("\"'")
    raise ProjectorError(f"{path}: unclosed YAML frontmatter")


def title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback.rsplit("/", 1)[-1].replace("-", " ").title()


class ProjectStore:
    def __init__(
        self,
        cwd: Path,
        root: Optional[Path] = None,
        projects_dir: Optional[Path] = None,
    ) -> None:
        self.root = (root or discover_git_root(cwd)).resolve()
        if projects_dir is None:
            self.projects_dir = self.root / "docs" / "projects"
        elif projects_dir.is_absolute():
            self.projects_dir = projects_dir.resolve()
        else:
            self.projects_dir = (self.root / projects_dir).resolve()

    def _project_from_path(self, path: Path) -> Project:
        relative = path.parent.relative_to(self.projects_dir).as_posix()
        if relative == "." or not valid_name(relative):
            raise ProjectorError(f"{path}: invalid project name {relative!r}")
        text = path.read_text(encoding="utf-8")
        metadata, _ = parse_frontmatter(text, path)
        status = metadata.get("status")
        if status not in STATUSES:
            choices = "|".join(STATUSES)
            raise ProjectorError(f"{path}: status must be one of {choices}")
        return Project(
            name=relative,
            title=title_from_text(text, relative),
            status=status,
            owner=metadata.get("owner"),
            path=path,
        )

    def _entry_points(self) -> list[Path]:
        if not self.projects_dir.exists():
            return []
        paths: list[Path] = []
        for directory, _, filenames in os.walk(self.projects_dir):
            if "readme.md" in filenames:
                paths.append(Path(directory) / "readme.md")
        return sorted(paths)

    def projects(self) -> list[Project]:
        if not self.projects_dir.exists():
            return []
        found: dict[str, Project] = {}
        for path in self._entry_points():
            project = self._project_from_path(path)
            folded = project.name.casefold()
            if folded in found:
                raise AmbiguousProject(
                    f"ambiguous project names: {found[folded].name}, {project.name}"
                )
            found[folded] = project
        return sorted(found.values(), key=lambda project: project.name)

    def resolve(self, name: str) -> Project:
        exact = [project for project in self.projects() if project.name == name]
        if exact:
            return exact[0]
        folded = [
            project for project in self.projects() if project.name.casefold() == name.casefold()
        ]
        if len(folded) > 1:
            raise AmbiguousProject(f"ambiguous project: {name}")
        if folded:
            return folded[0]
        raise ProjectNotFound(f"project not found: {name}")

    def init(self) -> Path:
        target = self.projects_dir / "README.md"
        if self.projects_dir.exists() and any(self.projects_dir.iterdir()):
            if target.exists():
                raise ProjectorError(f"project convention already exists: {target}")
            raise ProjectorError(
                f"refusing to overwrite an existing project system: {self.projects_dir}"
            )
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        template = resources.files("projector").joinpath(
            "templates/project-readme.md"
        ).read_text(encoding="utf-8")
        self._create_exclusive(target, template)
        return target

    def create(self, name: str, status: str = "later", parent: str | None = None) -> Project:
        if parent:
            if "/" in name or not valid_name(name):
                raise ProjectorError("--parent requires one valid project name segment")
            self.resolve(parent)
            name = f"{parent}/{name}"
        if not valid_name(name):
            raise ProjectorError(
                "project names use lowercase letters, digits, hyphens, and slashes"
            )
        if status not in STATUSES:
            raise ProjectorError(f"invalid status: {status}")
        path = self.projects_dir / name / "readme.md"
        if path.exists() or any(
            candidate.name.lower() == "readme.md" for candidate in path.parent.glob("*")
        ):
            raise ProjectorError(f"project already exists: {name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        title = name.rsplit("/", 1)[-1].replace("-", " ").title()
        body = (
            f"---\nstatus: {status}\n---\n\n# {title}\n\n"
            "## 1. Outcome\n\nDescribe the result this project produces.\n\n"
            "## 2. Acceptance criteria\n\n"
            "- Define the evidence that proves the project is complete.\n"
        )
        self._create_exclusive(path, body)
        return self._project_from_path(path)

    @staticmethod
    def _create_exclusive(path: Path, content: str) -> None:
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError as error:
            raise ProjectorError(f"refusing to overwrite: {path}") from error
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)

    def set_status(self, name: str, status: str) -> tuple[Project, bool]:
        if status not in STATUSES:
            raise ProjectorError(f"invalid status: {status}")
        project = self.resolve(name)
        before = project.path.read_text(encoding="utf-8")
        original_stat = project.path.stat()
        metadata, _ = parse_frontmatter(before, project.path)
        if metadata.get("status") == status:
            return project, False
        match = STATUS_LINE.search(before)
        if not match or match.group("value").strip().strip("\"'") != project.status:
            raise ProjectorError(f"{project.path}: cannot update status safely")
        after = before[: match.start("value")] + status + before[match.end("value") :]
        current_stat = project.path.stat()
        signature = (original_stat.st_ino, original_stat.st_size, original_stat.st_mtime_ns)
        current = (current_stat.st_ino, current_stat.st_size, current_stat.st_mtime_ns)
        if signature != current:
            raise ProjectorError(f"{project.path}: changed while it was being read")
        self._atomic_write(project.path, after)
        return self.resolve(name), True

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(content)
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def search(self, query: str, status: str | None = None) -> list[dict[str, object]]:
        projects = self.projects()
        roots = sorted(projects, key=lambda project: len(project.path.parts), reverse=True)
        matches: list[dict[str, object]] = []
        needle = query.casefold()
        for project in projects:
            metadata = " ".join(
                value for value in (project.name, project.title, project.status, project.owner) if value
            )
            if (not status or project.status == status) and needle in metadata.casefold():
                matches.append(
                    {
                        "project": project.name,
                        "path": project.path.relative_to(self.root).as_posix(),
                        "line": 0,
                        "text": project.title,
                    }
                )
        for path in sorted(self.projects_dir.rglob("*.md")):
            if path == self.projects_dir / "README.md":
                continue
            owner = next(
                (project for project in roots if path == project.path or project.path.parent in path.parents),
                None,
            )
            if owner is None or (status and owner.status != status):
                continue
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if needle in line.casefold():
                    matches.append(
                        {
                            "project": owner.name,
                            "path": path.relative_to(self.root).as_posix(),
                            "line": line_number,
                            "text": line.strip(),
                        }
                    )
        return matches

    def check(self) -> list[Issue]:
        issues: list[Issue] = []
        if not self.projects_dir.exists():
            return [Issue("missing-projects-dir", self._relative(self.projects_dir), "directory does not exist")]

        top_level = [path for path in self.projects_dir.iterdir() if path.is_dir()]
        for directory in sorted(top_level):
            if not any(child.name == "readme.md" and child.is_file() for child in directory.iterdir()):
                issues.append(
                    Issue(
                        "missing-plan",
                        self._relative(directory),
                        "top-level project directory has no lowercase readme.md",
                    )
                )

        seen_case: dict[str, str] = {}
        wrong_case_paths: set[str] = set()
        for path in sorted(self.projects_dir.rglob("*")):
            if path.is_symlink():
                issues.append(Issue("symlink", self._relative(path), "project trees cannot contain symlinks"))
            if (
                path.parent != self.projects_dir
                and path.is_file()
                and path.name.lower() == "readme.md"
                and path.name != "readme.md"
            ):
                wrong_case_paths.add(self._relative(path))
                issues.append(
                    Issue("wrong-entry-case", self._relative(path), "project entry point must be lowercase readme.md")
                )
            relative = path.relative_to(self.projects_dir).as_posix()
            folded = relative.casefold()
            if folded in seen_case and seen_case[folded] != relative:
                issues.append(
                    Issue("case-collision", relative, f"collides with {seen_case[folded]}")
                )
            seen_case[folded] = relative

        for relative in self._tracked_paths():
            name = Path(relative).name
            full_path = (Path(self._relative(self.projects_dir)) / relative).as_posix()
            if (
                name.lower() == "readme.md"
                and name != "readme.md"
                and Path(relative).parent != Path(".")
                and full_path not in wrong_case_paths
            ):
                issues.append(
                    Issue(
                        "wrong-entry-case",
                        full_path,
                        "Git records the project entry point with casing other than readme.md",
                    )
                )

        projects: list[Project] = []
        names: dict[str, str] = {}
        for path in self._entry_points():
            try:
                project = self._project_from_path(path)
                folded = project.name.casefold()
                if folded in names:
                    raise AmbiguousProject(
                        f"ambiguous project names: {names[folded]}, {project.name}"
                    )
                names[folded] = project.name
                projects.append(project)
            except ProjectorError as error:
                issues.append(Issue("invalid-project", self._relative(path), str(error)))

        for path in sorted(self.projects_dir.rglob("*.md")):
            if any(path == project.path or project.path.parent in path.parents for project in projects):
                issues.extend(self._check_links(path))
        return issues

    def _check_links(self, path: Path) -> list[Issue]:
        issues: list[Issue] = []
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            for raw_target in LINK.findall(line):
                target = raw_target.strip().split(maxsplit=1)[0].strip("<>\"'")
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                candidate = (path.parent / unquote(parsed.path)).resolve()
                if not self._exact_path_exists(candidate):
                    issues.append(
                        Issue(
                            "broken-project-link",
                            f"{self._relative(path)}:{line_number}",
                            f"target does not exist: {target}",
                        )
                    )
            if line.count("](") > len(LINK.findall(line)):
                issues.append(
                    Issue(
                        "malformed-project-link",
                        f"{self._relative(path)}:{line_number}",
                        "malformed Markdown link",
                    )
                )
        return issues

    def _tracked_paths(self) -> list[str]:
        try:
            prefix = self.projects_dir.relative_to(self.root).as_posix()
        except ValueError:
            return []
        result = subprocess.run(
            ["git", "-C", str(self.root), "ls-files", "-z", "--", prefix],
            check=False,
            capture_output=True,
        )
        if result.returncode:
            return []
        paths = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
        prefix_with_slash = f"{prefix}/"
        return [path[len(prefix_with_slash) :] for path in paths if path.startswith(prefix_with_slash)]

    @staticmethod
    def _exact_path_exists(path: Path) -> bool:
        if not path.exists():
            return False
        current = Path(path.anchor)
        for part in path.parts[1:]:
            try:
                names = {entry.name for entry in current.iterdir()}
            except (FileNotFoundError, NotADirectoryError, PermissionError):
                return False
            if part not in names:
                return False
            current /= part
        return True

    def _relative(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

def json_text(payload: dict[str, object]) -> str:
    return json.dumps({"schema_version": 1, **payload}, indent=2, sort_keys=True)


def grouped_projects(projects: Iterable[Project]) -> str:
    rows: list[str] = []
    for status in STATUSES:
        group = [project for project in projects if project.status == status]
        if not group:
            continue
        rows.append(f"{status}:")
        rows.extend(
            f"  {project.name:<28} {project.title}"
            + (f" [{project.owner}]" if project.owner else "")
            for project in group
        )
    return "\n".join(rows)
