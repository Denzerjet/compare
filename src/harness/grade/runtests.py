"""Invoke django's test suite for a task and return parsed outcomes."""

from __future__ import annotations

from pathlib import Path

from ..env import workspace
from ..schema import Task
from .parse import ParsedRun, parse_run

DEFAULT_TIMEOUT_SEC = 1800


def build_argv(test_labels: list[str], *, verbosity: int = 2) -> list[str]:
    """The exact command run inside the container.

    --parallel 1 is mandatory, not a default. Under --parallel > 1 django hands
    tests to worker processes and ships results back through RemoteTestResult,
    which pickles a fixed set of fields and would bypass the injected
    collector entirely -- outcomes would come back empty with no error.
    """
    return [
        "python", "tests/runtests.py",
        "--settings=harness_settings",
        "--parallel", "1",
        "--verbosity", str(verbosity),
        *test_labels,
    ]


def run_labels(
    tree: Path,
    test_labels: list[str],
    *,
    out_dir: Path,
    image: str,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> ParsedRun:
    """Run bare test labels against a prepared worktree.

    Takes labels rather than a Task because validation needs to run tests
    *before* a Task exists: fail_to_pass is derived from what this observes, and
    a Task cannot be constructed with an empty fail_to_pass.
    """
    run = workspace.docker_run(
        build_argv(test_labels),
        tree=tree,
        out_dir=out_dir,
        image=image,
        timeout=timeout,
    )
    return parse_run(
        out_dir / "results.json",
        exit_code=run.exit_code,
        timed_out=run.timed_out,
        stdout=run.stdout,
        duration_sec=run.duration_sec,
    )


def run_tests(
    tree: Path,
    task: Task,
    *,
    out_dir: Path,
    image: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> ParsedRun:
    """Run the task's test labels against an already-prepared worktree."""
    return run_labels(
        tree,
        task.test_labels,
        out_dir=out_dir,
        image=image or task.env_image,
        timeout=timeout,
    )
