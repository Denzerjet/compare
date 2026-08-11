"""The tool surface the model works through.

Identical for every model -- same schemas, same bounds, same error strings. Any
per-model variation here would show up as a capability difference.

Every result is bounded. That is not only a cost lever: it is what makes
`context_exceeded` structurally near-impossible, since the worst-case transcript is
`prompt + max_steps x (max_output + max_result)` and the bound is derived from the
smallest context window in the model set (see config/models.yaml).

Writes are confined to `django/`. Grading reverts anything outside it anyway, so
enforcing it here only means the model finds out immediately instead of spending
steps on edits that will be silently discarded.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

WRITABLE_PREFIXES = ("django/",)


@dataclass
class ToolLimits:
    max_read_lines: int = 200
    max_grep_matches: int = 50
    max_list_entries: int = 200


def tool_schemas() -> list[dict]:
    """Tool definitions. Deterministic order so the prompt prefix stays cacheable."""
    return [
        {
            "name": "read_file",
            "description": (
                "Read a file from the repository. Returns numbered lines. Output is "
                "capped; when it truncates you are told how many lines remain, and "
                "can call again with a different start_line."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repo-relative path."},
                    "start_line": {"type": "integer", "description": "1-indexed, default 1."},
                },
                "required": ["path"],
            },
        },
        {
            "name": "grep",
            "description": (
                "Search file contents with a regular expression. Returns matching "
                "lines as path:line:text. Capped; a truncated result tells you the "
                "total match count so you can narrow the pattern or path."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Python regular expression."},
                    "path": {"type": "string", "description": "Directory or file to search. Default: django/"},
                },
                "required": ["pattern"],
            },
        },
        {
            "name": "list_dir",
            "description": "List the entries of a directory.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Repo-relative directory."}},
                "required": ["path"],
            },
        },
        {
            "name": "edit_file",
            "description": (
                "Replace an exact string in a file. old_string must appear exactly "
                "once. Only files under django/ may be edited."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string", "description": "Exact text to replace; must be unique in the file."},
                    "new_string": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    ]


class Tools:
    """Executes tool calls against one task's worktree."""

    def __init__(self, tree: Path, limits: ToolLimits | None = None):
        self.tree = Path(tree).resolve()
        self.limits = limits or ToolLimits()
        self.calls: list[str] = []

    # -- path safety ---------------------------------------------------------

    def _resolve(self, path: str) -> Path:
        """Resolve a model-supplied path, refusing anything outside the worktree.

        The path comes from model output, so it is untrusted: `..`, an absolute
        path, or a symlink could otherwise read or write the host filesystem.
        """
        candidate = (self.tree / path.lstrip("/")).resolve()
        if not candidate.is_relative_to(self.tree):
            raise ValueError(f"path escapes the repository: {path}")
        return candidate

    def _rel(self, p: Path) -> str:
        return str(p.relative_to(self.tree))

    # -- tools ---------------------------------------------------------------

    def read_file(self, path: str, start_line: int = 1) -> str:
        target = self._resolve(path)
        if not target.is_file():
            return f"Error: no such file: {path}"
        lines = target.read_text(errors="replace").splitlines()
        start = max(1, int(start_line))
        window = lines[start - 1 : start - 1 + self.limits.max_read_lines]
        body = "\n".join(f"{start + i:>6}\t{ln}" for i, ln in enumerate(window))
        shown_to = start - 1 + len(window)
        if shown_to < len(lines):
            body += (
                f"\n\n[truncated: showed lines {start}-{shown_to} of {len(lines)}; "
                f"call read_file with start_line={shown_to + 1} to continue]"
            )
        return body or f"[{path} is empty]"

    def grep(self, pattern: str, path: str = "django/") -> str:
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return f"Error: invalid regular expression: {exc}"
        root = self._resolve(path)
        files = [root] if root.is_file() else sorted(root.rglob("*.py"))
        hits: list[str] = []
        total = 0
        for f in files:
            try:
                for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                    if rx.search(line):
                        total += 1
                        if len(hits) < self.limits.max_grep_matches:
                            hits.append(f"{self._rel(f)}:{n}:{line.strip()[:200]}")
            except OSError:
                continue
        if not hits:
            return f"No matches for {pattern!r} under {path}"
        out = "\n".join(hits)
        if total > len(hits):
            out += f"\n\n[truncated: {len(hits)} of {total} matches shown]"
        return out

    def list_dir(self, path: str) -> str:
        target = self._resolve(path)
        if not target.is_dir():
            return f"Error: not a directory: {path}"
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
        shown = entries[: self.limits.max_list_entries]
        out = "\n".join(f"{'  ' if e.is_file() else 'd '}{e.name}" for e in shown)
        if len(entries) > len(shown):
            out += f"\n[truncated: {len(shown)} of {len(entries)}]"
        return out or "[empty directory]"

    def edit_file(self, path: str, old_string: str, new_string: str) -> str:
        rel = path.lstrip("/")
        if not rel.startswith(WRITABLE_PREFIXES):
            # Told immediately rather than reverted silently at grade time.
            return (
                f"Error: only files under django/ may be edited; {rel} is outside "
                f"that. Changes elsewhere are discarded before grading."
            )
        target = self._resolve(path)
        if not target.is_file():
            return f"Error: no such file: {path}"
        text = target.read_text(errors="replace")
        count = text.count(old_string)
        if count == 0:
            return "Error: old_string not found in the file. It must match exactly, including whitespace."
        if count > 1:
            return f"Error: old_string appears {count} times; it must be unique. Include surrounding context."
        target.write_text(text.replace(old_string, new_string, 1))
        return f"Edited {rel}."

    def dispatch(self, name: str, args: dict) -> tuple[str, bool]:
        """Run a tool call. Returns (result_text, is_error).

        Exceptions become error strings rather than propagating: a bad argument is
        the model's problem to recover from, not a reason to abort a paid run. Only
        a defect in this file should ever raise, and that is a harness error.
        """
        self.calls.append(name)
        try:
            fn = {
                "read_file": self.read_file,
                "grep": self.grep,
                "list_dir": self.list_dir,
                "edit_file": self.edit_file,
            }.get(name)
            if fn is None:
                return f"Error: unknown tool {name!r}", True
            out = fn(**args)
            return out, out.startswith("Error:")
        except TypeError as exc:
            return f"Error: bad arguments for {name}: {exc}", True
        except ValueError as exc:
            return f"Error: {exc}", True
