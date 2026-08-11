"""Split a django commit into the two halves a task needs.

    test.patch      everything the commit changed under tests/
    solution.patch  everything it changed under django/

Deliberately NOT here: deriving fail_to_pass / pass_to_pass. Those are *observed*
by validate.py, not inferred from the diff. Every heuristic for guessing them
breaks on real django commits -- the fix commit may modify an existing
parameterised test rather than add one, may add coverage for behaviour that
already worked, or may be the tail commit of a ticket whose parent already
contains the fix. Running the tests at base_commit answers all of those directly.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .scan import DEFAULT_REPO, Candidate


@dataclass
class Split:
    test_patch: str
    solution_patch: str
    test_labels: list[str]
    dropped_files: list[str]

    @property
    def complete(self) -> bool:
        """False when the commit changed files outside django/ and tests/.

        Those changes are dropped, so solution.patch may be an incomplete
        rendering of the fix. Not fatal -- docs and release notes are the usual
        cause and they don't affect tests -- but it's the one way a task can be
        unsolvable through no fault of the model, so it is recorded and validation
        run 2 is what actually catches it.
        """
        return not self.dropped_files


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def base_commit(sha: str, repo: Path | None = None) -> str:
    return _git(Path(repo or DEFAULT_REPO), "rev-parse", f"{sha}^").strip()


def test_labels_for(test_files: list[str]) -> list[str]:
    """Map changed test paths to labels `runtests.py` accepts.

    Module-level where possible: measured at 1-3s per run versus 20s+ for a whole
    package, which matters across ~1000 validation runs. A supporting file
    (models.py, urls.py) falls back to its package, but only when no test module
    in that same package was also touched -- if one was, running it exercises the
    supporting change anyway.
    """
    modules: set[str] = set()
    packages: set[str] = set()
    touched_packages: set[str] = set()

    for path in test_files:
        parts = Path(path).parts
        if len(parts) < 2 or parts[0] != "tests":
            continue
        pkg = parts[1]
        name = parts[-1]
        if not name.endswith(".py"):
            # A fixture or data file: its package is the safe unit.
            packages.add(pkg)
            continue
        stem = name[:-3]
        if stem.startswith("test_") or stem == "tests":
            modules.add(".".join(parts[1:-1] + (stem,)))
            touched_packages.add(pkg)
        else:
            packages.add(pkg)

    # Drop package labels made redundant by a module label in the same package.
    packages -= touched_packages
    return sorted(modules | packages)


def split(cand: Candidate, repo: Path | None = None) -> Split:
    repo = Path(repo or DEFAULT_REPO)
    test_patch = _git(repo, "show", cand.sha, "--", "tests/")
    solution_patch = _git(repo, "show", cand.sha, "--", "django/")
    return Split(
        test_patch=test_patch,
        solution_patch=solution_patch,
        test_labels=test_labels_for(cand.test_files),
        dropped_files=sorted(cand.other_files),
    )
