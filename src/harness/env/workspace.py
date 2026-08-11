"""Per-task filesystem and container setup.

Two primitives: a disposable git worktree pinned to a task's base commit, and a
container invocation against it. Nothing here knows about grading or models.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[3]
INJECT_DIR = Path(__file__).resolve().parent / "inject"
DEFAULT_REPO = HARNESS_ROOT / "repo" / "django"


class PatchError(RuntimeError):
    """A patch failed to apply. Distinct from a test failure."""


@dataclass
class ContainerRun:
    exit_code: int
    stdout: str
    duration_sec: float
    timed_out: bool


@contextmanager
def worktree(base_commit: str, repo: Path | None = None, keep: bool = False):
    """Check out `base_commit` into a throwaway worktree.

    A worktree rather than a clone: it shares the object store, so setup is
    fast and disk stays flat across 100 tasks.
    """
    repo = Path(repo or DEFAULT_REPO)
    path = Path(tempfile.gettempdir()) / f"harness-wt-{uuid.uuid4().hex[:12]}"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--quiet", "--detach",
         str(path), base_commit],
        check=True, capture_output=True, text=True,
    )
    try:
        yield path
    finally:
        if keep:
            return
        # `worktree remove` refuses when the tree is dirty, which it always is
        # after patching, hence --force. The rmtree is a backstop for the case
        # where git has already forgotten the worktree.
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "remove", "--force", str(path)],
            capture_output=True, text=True,
        )
        shutil.rmtree(path, ignore_errors=True)


def apply_patch(tree: Path, patch: str, *, label: str) -> None:
    proc = subprocess.run(
        ["git", "apply", "--verbose", "-"],
        cwd=tree, input=patch, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise PatchError(f"{label} failed to apply:\n{proc.stderr.strip()}")


def restore_outside(tree: Path, allowed_prefixes: tuple[str, ...]) -> list[str]:
    """Undo every change outside `allowed_prefixes`; return what was stripped.

    A whitelist rather than a `tests/` blacklist, because blacklisting one
    directory is not enough. /testbed/tests is sys.path[0] (it holds
    runtests.py) and /testbed precedes /harness on PYTHONPATH, so a patch that
    *creates* tests/harness_settings.py or /testbed/harness_settings.py shadows
    the injected settings module, takes over TEST_RUNNER, and can write a
    results.json claiming a clean pass without running anything. Verified
    exploitable before this existed.

    Note both halves are needed: `git checkout` restores tracked files but
    leaves untracked ones behind, and the shadowing attack works by *adding* a
    file.
    """
    entries = _status_entries(tree)
    stripped: list[str] = []
    for status, path in entries:
        if path.startswith(allowed_prefixes):
            continue
        stripped.append(path)
        if status.startswith("?"):
            target = tree / path
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
        else:
            # `checkout HEAD --` (not `checkout --`) so staged changes are
            # reverted too, and deletions are restored.
            subprocess.run(
                ["git", "checkout", "HEAD", "--", path],
                cwd=tree, capture_output=True, text=True,
            )
    return sorted(stripped)


def _status_entries(tree: Path) -> list[tuple[str, str]]:
    """[(status, path)] from `git status --porcelain -z`, renames flattened."""
    proc = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
        cwd=tree, check=True, capture_output=True, text=True,
    )
    tokens = [t for t in proc.stdout.split("\0") if t]
    entries: list[tuple[str, str]] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        status, path = token[:2], token[3:]
        entries.append((status, path))
        # A rename emits the source path as a separate NUL-delimited token,
        # which must also be restored or the original file stays deleted.
        if "R" in status and i + 1 < len(tokens):
            entries.append((status, tokens[i + 1]))
            i += 1
        i += 1
    return entries


def diff(tree: Path) -> str:
    """The worktree's current changes, as the patch a model would be credited with."""
    proc = subprocess.run(
        ["git", "diff"], cwd=tree, check=True, capture_output=True, text=True
    )
    return proc.stdout


def docker_run(
    argv: list[str],
    *,
    tree: Path,
    out_dir: Path,
    image: str,
    timeout: int,
    network: bool = False,
) -> ContainerRun:
    """Run `argv` in the eval image with the worktree mounted at /testbed.

    Networking is off by default: a graded run must not be able to reach the
    internet, or results stop being reproducible.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{tree}:/testbed",
        "-v", f"{INJECT_DIR}:/harness:ro",
        "-v", f"{out_dir}:/harness_out",
        "-e", "HARNESS_RESULT_PATH=/harness_out/results.json",
        "-w", "/testbed",
    ]
    if not network:
        cmd += ["--network", "none"]
    cmd += [image, *argv]

    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return ContainerRun(
            exit_code=proc.returncode,
            stdout=proc.stdout + proc.stderr,
            duration_sec=time.monotonic() - started,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        captured = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(captured, bytes):
            captured = captured.decode("utf-8", "replace")
        return ContainerRun(
            exit_code=-1,
            stdout=captured,
            duration_sec=time.monotonic() - started,
            timed_out=True,
        )
