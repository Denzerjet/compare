"""Turn a candidate commit into a trusted task, or reject it with a reason.

Two container runs, deliberately asymmetric in what they buy:

  Run 1  base_commit + test.patch
         Observes which tests fail. That observation *is* fail_to_pass -- it is
         never inferred from the diff. Rejects the high-yield failure mode: a
         task that was never broken, which in grading output is indistinguishable
         from a real solve.

  Run 2  base_commit + solution.patch + test.patch
         Confirms django's own fix turns those failures green *in this image*.
         Low-yield but high-consequence, and the only thing that ever exercises
         mine/split.py -- a bad split or a fix needing something absent from this
         sqlite-only image yields a task that fails 100% of models while looking
         exactly like a very hard one.

There is deliberately no third run. See README -> Validation.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .env import workspace
from .env.workspace import PatchError
from .grade import RETRIABLE, diff_loc
from .grade.parse import FAILING, PASSING, ParsedRun, RunStatus
from .grade.runtests import run_labels
from .mine.scan import Candidate
from .mine.split import Split, base_commit

DEFAULT_IMAGE = "harness/django:py313-v1"
MAX_RETRIES = 2

# A task is rejected if its graded configuration runs slower than this. Measured
# on run 2, which uses the same narrowed labels grading will use, so the figure is
# exactly what each model will pay per task.
MAX_GRADED_RUNTIME_SEC = 60
# Deliberately far above the acceptance threshold. If the two were equal, a slow
# task would be killed and recorded as harness_error instead of cleanly rejected
# as too_slow -- we need to *measure* it to reject it.
KILL_TIMEOUT_SEC = 300

FAILED_IMPORT_PREFIX = "unittest.loader._FailedTest."


def resolve_modules(test_ids: set[str], known_labels: list[str]) -> tuple[list[str], list[str]]:
    """Map failing test ids to runnable module labels.

    Returns (resolved, unresolvable). The second list must be empty for the task
    to be usable -- a label django cannot match runs *nothing* and silently drops
    those tests from the task, which is worse than an error.

    The case that forces this: when a module fails to import, unittest names the
    synthetic test with the module's SHORT name, so the id is
    `unittest.loader._FailedTest.test_parallel`, not
    `...._FailedTest.test_runner.test_parallel`. Stripping the prefix yields
    `test_parallel`, which matches no django label. The commit's own touched test
    modules are the authority for reconstructing the full path.
    """
    resolved, unresolvable = set(), set()
    for test_id in test_ids:
        name = module_of(test_id)
        if name in known_labels:
            resolved.add(name)
            continue
        # A short name reconstructs against the modules this commit touched.
        matches = [lbl for lbl in known_labels if lbl.endswith("." + name)]
        if len(matches) == 1:
            resolved.add(matches[0])
        elif matches:
            unresolvable.add(f"{name} (ambiguous: {sorted(matches)})")
        else:
            unresolvable.add(name)
    return sorted(resolved), sorted(unresolvable)


def module_of(test_id: str) -> str:
    """The test module a test id belongs to.

    Normally `module.Class.method` -> drop the last two components. The exception
    is a module that failed to import: unittest reports one synthetic
    `unittest.loader._FailedTest.<module>` id, where the module is the *suffix*,
    not the prefix. Getting that wrong scopes the run to `unittest.loader`, which
    matches nothing.
    """
    if test_id.startswith(FAILED_IMPORT_PREFIX):
        return test_id[len(FAILED_IMPORT_PREFIX):]
    parts = test_id.split(".")
    return ".".join(parts[:-2]) if len(parts) > 2 else test_id


class Reject(str, Enum):
    """Why a candidate didn't become a task. Every rejection is logged with one
    of these so the funnel is auditable rather than a bare survivor count."""

    NO_FAILING_TESTS = "no_failing_tests"          # never broken -> free credit
    TEST_PATCH_FAILED = "test_patch_failed"        # test.patch didn't apply
    SOLUTION_PATCH_FAILED = "solution_patch_failed"
    FIX_DOES_NOT_RESOLVE = "fix_does_not_resolve"  # reference fix insufficient here
    FIX_BREAKS_TESTS = "fix_breaks_tests"          # reference fix regresses others
    NO_PASSING_TESTS = "no_passing_tests"          # no regression baseline
    UNRESOLVED_LABEL = "unresolved_label"          # derived module isn't runnable
    TOO_SLOW = "too_slow"
    HARNESS_ERROR = "harness_error"                # survived retries


@dataclass
class ValidationResult:
    candidate: Candidate
    ok: bool
    reject: Reject | None = None
    detail: str = ""
    fail_to_pass: list[str] = field(default_factory=list)
    pass_to_pass: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    # Narrowed to the modules containing failures -- this is what grading runs.
    test_labels: list[str] = field(default_factory=list)
    graded_runtime_sec: float = 0.0
    base: str = ""
    runtime_sec: float = 0.0
    harness_retries: int = 0
    reference_loc: int = 0

    @property
    def summary(self) -> str:
        if self.ok:
            return (
                f"OK  f2p={len(self.fail_to_pass)} p2p={len(self.pass_to_pass)} "
                f"{self.graded_runtime_sec:.1f}s graded"
            )
        return f"REJECT[{self.reject.value}] {self.detail[:70]}"


def _run_with_retry(
    tree: Path, labels: list[str], *, image: str, timeout: int
) -> tuple[ParsedRun, int]:
    """Re-run when the container produces no usable result.

    Free: no inference is involved at validation time. Without it, a contention
    hiccup on a loaded machine silently discards a good task -- and we measured
    exactly that (a module failing after a heavy neighbour, passing alone).
    """
    retries = 0
    while True:
        with tempfile.TemporaryDirectory(prefix="harness-val-") as out:
            parsed = run_labels(
                tree, labels, out_dir=Path(out), image=image, timeout=timeout
            )
        if parsed.trustworthy or retries >= MAX_RETRIES:
            return parsed, retries
        if parsed.status is RunStatus.TIMEOUT or parsed.status not in RETRIABLE:
            return parsed, retries
        retries += 1


def validate(
    cand: Candidate,
    sp: Split,
    *,
    repo: Path | None = None,
    image: str = DEFAULT_IMAGE,
    max_graded_runtime_sec: int = MAX_GRADED_RUNTIME_SEC,
) -> ValidationResult:
    base = base_commit(cand.sha, repo=repo)
    res = ValidationResult(
        candidate=cand, ok=False, base=base, reference_loc=diff_loc(sp.solution_patch)
    )
    retries = 0

    # -- Run 1: is it actually broken? ---------------------------------------
    with workspace.worktree(base, repo=repo) as tree:
        try:
            workspace.apply_patch(tree, sp.test_patch, label="test.patch")
        except PatchError as exc:
            res.reject, res.detail = Reject.TEST_PATCH_FAILED, str(exc)
            return res
        before, r = _run_with_retry(
            tree, sp.test_labels, image=image, timeout=KILL_TIMEOUT_SEC
        )
        retries += r

    if not before.trustworthy:
        res.reject, res.detail = Reject.HARNESS_ERROR, f"run 1: {before.detail[:200]}"
        res.harness_retries = retries
        return res

    passing_before = {t for t, s in before.outcomes.items() if s in PASSING}
    failing_before = {t for t, s in before.outcomes.items() if s in FAILING}
    # Skipped tests are asserted on in neither direction: a backend-gated test is
    # skipped rather than failed on sqlite, and treating that as either would be
    # a lie about what ran.
    res.skipped = sorted(set(before.outcomes) - passing_before - failing_before)

    # Cheap exit: if literally everything passed at base there is nothing a fix
    # could turn green, so run 2 cannot produce a fail_to_pass set. Saves a
    # container on the most common rejection.
    if not failing_before:
        res.reject = Reject.NO_FAILING_TESTS
        res.detail = (
            f"{len(passing_before)} tests all pass at base_commit -- nothing to "
            f"fix, so every model would score this by doing nothing"
        )
        res.harness_retries = retries
        return res
    if not passing_before:
        res.reject = Reject.NO_PASSING_TESTS
        res.detail = "no passing tests to form a regression baseline"
        res.harness_retries = retries
        return res

    # Narrow to the modules that actually contain a failure. A commit's touched
    # test files often pull in a whole package (`cache` dragged in 1,135 tests in
    # one measured case); the modules holding the failures are the real blast
    # radius, and this is the label set grading will use, so the saving compounds
    # across 100 tasks x N models.
    failing_modules, unresolvable = resolve_modules(failing_before, sp.test_labels)
    if unresolvable:
        res.reject = Reject.UNRESOLVED_LABEL
        res.detail = (
            f"cannot map failing tests to runnable labels: {unresolvable[:3]} "
            f"(commit touched {sp.test_labels})"
        )
        res.harness_retries = retries
        return res
    res.test_labels = failing_modules

    # -- Run 2: does django's own fix resolve it in THIS image? ---------------
    with workspace.worktree(base, repo=repo) as tree:
        try:
            workspace.apply_patch(tree, sp.solution_patch, label="solution.patch")
        except PatchError as exc:
            res.reject, res.detail = Reject.SOLUTION_PATCH_FAILED, str(exc)
            res.harness_retries = retries
            return res
        workspace.apply_patch(tree, sp.test_patch, label="test.patch")
        after, r = _run_with_retry(
            tree, failing_modules, image=image, timeout=KILL_TIMEOUT_SEC
        )
        retries += r
    res.graded_runtime_sec = after.duration_sec

    res.harness_retries = retries
    if not after.trustworthy:
        res.reject, res.detail = Reject.HARNESS_ERROR, f"run 2: {after.detail[:200]}"
        return res

    passing_after = {t for t, s in after.outcomes.items() if s in PASSING}

    # Set difference across the two runs, NOT "did run 1's failures now pass".
    # A test file whose new cases reference an API the fix introduces cannot even
    # import at base_commit, so unittest reports one synthetic
    # `unittest.loader._FailedTest.<module>` id instead of the real tests. That id
    # ceases to exist once the module imports, so keying on run 1's ids marks it
    # permanently unresolved and rejects a perfectly good task. Defining
    # fail_to_pass as "passes now, didn't before" is robust to that, and to tests
    # that only exist after test.patch.
    in_scope = set(failing_modules)
    res.fail_to_pass = sorted(passing_after - passing_before)
    # Regression coverage is the passing tests of the failing modules only. Tests
    # from modules with no failure are dropped: they are not in the blast radius
    # and run 2 no longer executes them, so asserting on them would be asserting
    # on tests that never ran.
    res.pass_to_pass = sorted(
        t for t in (passing_before & passing_after) if module_of(t) in in_scope
    )
    regressed = sorted(
        t for t in (passing_before - passing_after) if module_of(t) in in_scope
    )

    if after.duration_sec > max_graded_runtime_sec:
        res.reject = Reject.TOO_SLOW
        res.detail = (
            f"graded config runs in {after.duration_sec:.0f}s, over the "
            f"{max_graded_runtime_sec}s budget ({len(failing_modules)} modules)"
        )
        return res

    if not res.fail_to_pass:
        res.reject = Reject.FIX_DOES_NOT_RESOLVE
        res.detail = (
            f"reference fix turns nothing green; {len(failing_before)} still "
            f"failing e.g. {sorted(failing_before)[:2]}"
        )
        return res
    if regressed:
        res.reject = Reject.FIX_BREAKS_TESTS
        res.detail = f"reference fix breaks: {regressed[:3]}"
        return res

    res.ok = True
    return res
