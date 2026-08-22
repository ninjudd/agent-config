from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from .core import (
    STATUSES,
    EnvironmentError,
    ProjectorError,
    ProjectStore,
    grouped_projects,
    json_text,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="projector")
    result.add_argument("--root", type=Path, help="Git repository root")
    result.add_argument(
        "--projects-dir",
        type=Path,
        help="project directory, relative to the Git root unless absolute",
    )
    subcommands = result.add_subparsers(dest="command", required=True)

    add_output(subcommands.add_parser("init", help="adopt the project convention"))

    listing = subcommands.add_parser("list", help="list projects")
    listing.add_argument("--status", choices=STATUSES)
    add_output(listing)

    show = subcommands.add_parser("show", help="show one project")
    show.add_argument("project")
    add_output(show)

    search = subcommands.add_parser("search", help="search project content")
    search.add_argument("query")
    search.add_argument("--status", choices=STATUSES)
    add_output(search)

    create = subcommands.add_parser("create", help="create a project")
    create.add_argument("project")
    create.add_argument("--status", choices=STATUSES, default="later")
    create.add_argument("--parent")
    create.add_argument("--no-edit", action="store_true")
    add_output(create)

    edit = subcommands.add_parser("edit", help="open a project plan")
    edit.add_argument("project")

    status = subcommands.add_parser("status", help="change project status")
    status.add_argument("project")
    status.add_argument("status", choices=STATUSES)
    add_output(status)

    done = subcommands.add_parser("done", help="mark a project done")
    done.add_argument("project")
    add_output(done)

    add_output(subcommands.add_parser("check", help="validate all projects"))
    return result


def add_output(command: argparse.ArgumentParser) -> None:
    command.add_argument("--json", action="store_true", dest="json_output")


def open_editor(path: Path) -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise EnvironmentError("an interactive terminal is required to open an editor")
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        raise EnvironmentError("set VISUAL or EDITOR before opening a project")
    try:
        subprocess.run([*shlex.split(editor), str(path)], check=True)
    except FileNotFoundError as error:
        raise EnvironmentError(f"editor not found: {editor}") from error
    except subprocess.CalledProcessError as error:
        raise EnvironmentError(f"editor exited with status {error.returncode}") from error


def emit_path(store: ProjectStore, path: Path, json_output: bool, action: str) -> None:
    relative = store._relative(path)
    if json_output:
        print(json_text({"action": action, "path": relative}))
    else:
        print(relative)


def run(arguments: argparse.Namespace) -> int:
    store = ProjectStore(Path.cwd(), arguments.root, arguments.projects_dir)
    command = arguments.command

    if command == "init":
        emit_path(store, store.init(), arguments.json_output, "created")
    elif command == "list":
        projects = store.projects()
        if arguments.status:
            projects = [project for project in projects if project.status == arguments.status]
        if arguments.json_output:
            print(json_text({"projects": [project.public(store.root) for project in projects]}))
        else:
            print(grouped_projects(projects))
    elif command == "show":
        project = store.resolve(arguments.project)
        content = store._read_text(project.path)
        if arguments.json_output:
            print(json_text({"project": {**project.public(store.root), "content": content}}))
        else:
            print(content, end="" if content.endswith("\n") else "\n")
    elif command == "search":
        matches = store.search(arguments.query, arguments.status)
        if arguments.json_output:
            print(json_text({"matches": matches}))
        else:
            for match in matches:
                print(f"{match['project']}\t{match['path']}:{match['line']}\t{match['text']}")
    elif command == "create":
        project = store.create(arguments.project, arguments.status, arguments.parent)
        emit_path(store, project.path, arguments.json_output, "created")
        if not arguments.no_edit and sys.stdin.isatty() and sys.stdout.isatty():
            open_editor(project.path)
    elif command == "edit":
        open_editor(store.resolve(arguments.project).path)
    elif command in ("status", "done"):
        new_status = arguments.status if command == "status" else "done"
        project, changed = store.set_status(arguments.project, new_status)
        emit_path(store, project.path, arguments.json_output, "updated" if changed else "unchanged")
        if command == "done":
            print("Record whether the project shipped, was abandoned, or was superseded.", file=sys.stderr)
    elif command == "check":
        issues = store.check()
        if arguments.json_output:
            print(json_text({"valid": not issues, "issues": [issue.__dict__ for issue in issues]}))
        elif issues:
            for issue in issues:
                print(f"{issue.path}: {issue.message} [{issue.code}]", file=sys.stderr)
        else:
            print("Project plans are valid.")
        return 0 if not issues else 65
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parser().parse_args(argv))
    except ProjectorError as error:
        print(f"projector: {error}", file=sys.stderr)
        return error.exit_code
    except (OSError, UnicodeDecodeError) as error:
        print(f"projector: {error}", file=sys.stderr)
        return 65


if __name__ == "__main__":
    raise SystemExit(main())
