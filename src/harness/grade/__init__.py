"""Grading: a pure function from (task, patch) to a verdict.

Nothing in this package knows which model produced a patch, or that a model was
involved at all. That keeps scoring identical across models and makes old runs
re-gradable after a grader fix without re-running inference.

The corollary is that token counts, cost, and step/termination data are NOT here
-- they are properties of the agent loop, recorded by run/ and merged into
results/<run_id>/<task_id>/grade.json at that layer. `Outcome` below covers only
what is observable from the patch and the test results.
"""

from __future__ import annotations

import tempfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from ..env import workspace
from ..env.workspace import PatchError
from ..schema import Task
from .parse import PASSING, ParsedRun, RunStatus
from .runtests import DEFAULT_TIMEOUT_SEC, run_tests

# The only paths a candidate patch is allowed to change. Everything else is
# reverted before the test patch is applied, so a patch cannot alter the tests
# it is judged by, nor plant a module that shadows the grading machinery.
ALLOWED_PATCH_PREFIXES = ("django/",)

# Inside the whitelist but worth flagging: this is django's own test framework,
# imported by the runner that grades the patch, so a change here could in
# principle influence outcomes rather than fix the bug. Some legitimate tasks do
# fix bugs here (e.g. django/test/client.py), so these are recorded for review
# rather than blocked.
SENSITIVE_PREFIXES = ("django/test/",)


class Outcome(str, Enum):
    """Why a graded attempt ended up where it did.

    A bare resolved=False flattens several very different behaviours into one
    bucket. Keeping them apart is what makes the LOC and cost aggregates
    readable: NO_PATCH would otherwise register as LOC 0 and read as
    'admirably surgical' when it means 'did nothing'.
    """

    RESOLVED = "resolved"              # target tests pass, nothing regressed
    REGRESSION = "regression"          # target fixed, but broke something else
    TESTS_FAILED = "tests_failed"      # patch applied, target still failing
    NO_PATCH = "no_patch"              # model produced an empty diff
    UNAPPLYABLE = "unapplyable"        # output was not a valid diff
    BASELINE = "baseline"              # no candidate patch: a validation run
    HARNESS_ERROR = "harness_error"    # no trustworthy result; not scored


def diff_loc(patch: str) -> int:
    """Added + deleted lines in a unified diff, excluding file headers.

    Used for BOTH the model's patch and the reference patch. Measuring them with
    the same function is the whole point -- a ratio between two differently
    computed numbers means nothing. Note this counts formatting churn as change,
    so the ratio is a noisy signal best read as a distribution rather than a
    threshold (django is black-formatted at 88 columns).
    """
    total = 0
    for line in patch.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith(("+", "-")):
            total += 1
    return total


def diff_hunks(patch: str) -> int:
    """Number of distinct edit sites in a unified diff (`@@` headers).

    A closer proxy than raw LOC for "how many separate places must be located and
    changed": a 40-line single-hunk edit is one site, a 12-line four-hunk edit is
    four. Recorded as a slicing dimension, not used for selection.
    """
    return sum(1 for line in patch.splitlines() if line.startswith("@@"))


@dataclass
class GradeResult:
    task_id: str
    resolved: bool
    status: RunStatus
    outcome: Outcome = Outcome.HARNESS_ERROR
    fail_to_pass: dict[str, str] = field(default_factory=dict)
    pass_to_pass: dict[str, str] = field(default_factory=dict)
    duration_sec: float = 0.0
    detail: str = ""
    # Size of the patch as graded -- i.e. after non-django/ paths are reverted,
    # since that is what actually ran. Recorded on failures too: a 400-line diff
    # that broke tests and a 2-line diff that fixed nothing are different
    # findings, and `outcome` above is what keeps them distinguishable.
    patch_loc: int = 0
    reference_loc: int = 0
    # Paths the patch touched outside ALLOWED_PATCH_PREFIXES, which were
    # reverted before grading. Recorded rather than discarded: a model that
    # keeps editing tests is a finding about that model, not just noise.
    stripped_paths: list[str] = field(default_factory=list)
    sensitive_paths: list[str] = field(default_factory=list)
    # How many times the container had to be re-run because it produced no
    # trustworthy result. Surviving errors are scored as failures, so this count
    # is the audit trail for whether the harness is depressing a score -- report
    # it per model, next to the resolve rate.
    harness_retries: int = 0
    # pass_to_pass tests that failed once and passed on confirmation. A genuinely
    # flaky test, not a regression the patch caused.
    flaky_tests: list[str] = field(default_factory=list)

    @property
    def loc_ratio(self) -> float | None:
        """Model patch size relative to django's own fix.

        None when there is no reference to compare against. Aggregate this over
        RESOLVED attempts only -- the ratio of a patch that didn't work is
        measuring something else.
        """
        if not self.reference_loc:
            return None
        return self.patch_loc / self.reference_loc

    @property
    def trustworthy(self) -> bool:
        """False means the run produced no usable answer, not that it failed."""
        return self.status is RunStatus.OK

    @property
    def all_fail_to_pass_passed(self) -> bool:
        return bool(self.fail_to_pass) and all(
            s in PASSING for s in self.fail_to_pass.values()
        )

    @property
    def all_pass_to_pass_passed(self) -> bool:
        return all(s in PASSING for s in self.pass_to_pass.values())

    @property
    def regressions(self) -> list[str]:
        """pass_to_pass tests the patch broke -- the interesting failure mode."""
        return sorted(t for t, s in self.pass_to_pass.items() if s not in PASSING)

    def to_dict(self) -> dict:
        out = asdict(self)
        out["status"] = self.status.value
        out["outcome"] = self.outcome.value
        out["regressions"] = self.regressions
        out["loc_ratio"] = self.loc_ratio
        return out


# Statuses worth re-running: they mean the container produced no usable answer,
# which on a contended machine is usually transient. TIMEOUT is deliberately
# excluded -- a repeat timeout is more likely a real infinite loop in the patched
# code than contention, and retrying it twice more wastes the full wall clock.
RETRIABLE = {RunStatus.NO_RESULTS, RunStatus.INCOMPLETE, RunStatus.MALFORMED}
MAX_HARNESS_RETRIES = 2
MAX_TIMEOUT_RETRIES = 1


def grade(
    task: Task,
    patch: str | None = None,
    *,
    repo: Path | None = None,
    image: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SEC,
    keep_tree: bool = False,
    confirm_regressions: bool = True,
) -> GradeResult:
    """Grade `patch`, re-running when the result isn't trustworthy.

    Two distinct retries, for two distinct signals:

      - **Harness error.** The container produced no usable result. Re-run; this
        is free because it re-runs against the already-computed patch, so no
        inference is repeated. Errors that survive are scored as failures and
        counted in `harness_retries`.
      - **Unexpected regression.** The run *was* trustworthy but reports a
        pass_to_pass test failing. Confirm it once before attributing it to the
        patch, since a genuinely flaky test would otherwise be recorded as a
        regression the model caused. Disagreement between the two runs marks the
        test flaky rather than picking a winner.
    """
    attempts = 0
    result = _grade_once(
        task, patch, repo=repo, image=image, timeout=timeout, keep_tree=keep_tree
    )

    while not result.trustworthy:
        limit = MAX_TIMEOUT_RETRIES if result.status is RunStatus.TIMEOUT else MAX_HARNESS_RETRIES
        if attempts >= limit or (
            result.status is not RunStatus.TIMEOUT and result.status not in RETRIABLE
        ):
            break
        attempts += 1
        result = _grade_once(
            task, patch, repo=repo, image=image, timeout=timeout, keep_tree=keep_tree
        )
    result.harness_retries = attempts

    if confirm_regressions and result.trustworthy and result.regressions:
        confirm = _grade_once(
            task, patch, repo=repo, image=image, timeout=timeout, keep_tree=keep_tree
        )
        if confirm.trustworthy:
            reproduced = set(result.regressions) & set(confirm.regressions)
            flaky = sorted(set(result.regressions) - reproduced)
            if flaky:
                # Only the confirmed failures stay attributed to the patch; the
                # rest are recorded as flaky and their verdict taken from the
                # run where they passed.
                for test in flaky:
                    result.pass_to_pass[test] = confirm.pass_to_pass.get(test, "passed")
                result.flaky_tests = flaky
                _reclassify(result)
    return result


def _grade_once(
    task: Task,
    patch: str | None = None,
    *,
    repo: Path | None = None,
    image: str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SEC,
    keep_tree: bool = False,
) -> GradeResult:
    """Apply `patch` to a fresh checkout of the task and report the verdict.

    Order of operations matters and is deliberate:
      1. worktree at base_commit
      2. apply the candidate patch (model output, or solution.patch)
      3. revert everything outside django/ -- discards test edits and any
         planted module that would shadow the grading machinery
      4. apply the task's test.patch
      5. run the task's test labels

    `patch=None` grades the unpatched state (a validation baseline). An empty or
    whitespace-only string is different: that is a model that produced nothing,
    and is reported as NO_PATCH.
    """
    reference_loc = diff_loc(task.solution_patch) if _has_solution(task) else 0
    is_baseline = patch is None
    empty_patch = patch is not None and not patch.strip()

    if empty_patch:
        # Nothing to apply and nothing to run: the verdict is knowable without
        # paying for a container.
        return GradeResult(
            task_id=task.task_id,
            resolved=False,
            status=RunStatus.OK,
            outcome=Outcome.NO_PATCH,
            reference_loc=reference_loc,
            detail="model produced an empty patch",
        )

    stripped: list[str] = []
    sensitive: list[str] = []
    patch_loc = 0

    with workspace.worktree(task.base_commit, repo=repo, keep=keep_tree) as tree:
        if not is_baseline:
            try:
                workspace.apply_patch(tree, patch, label="candidate patch")
            except PatchError as exc:
                # A patch that doesn't apply is a real, common model failure --
                # unresolved, not harness breakage. Recorded with the attempted
                # size so the failure is still inspectable.
                return GradeResult(
                    task_id=task.task_id,
                    resolved=False,
                    status=RunStatus.OK,
                    outcome=Outcome.UNAPPLYABLE,
                    patch_loc=diff_loc(patch),
                    reference_loc=reference_loc,
                    detail=str(exc),
                )
            stripped = workspace.restore_outside(tree, ALLOWED_PATCH_PREFIXES)
            sensitive = sorted(
                p for p in _changed_paths(tree) if p.startswith(SENSITIVE_PREFIXES)
            )
            # Measured after the strip, because that is the patch that runs.
            patch_loc = diff_loc(workspace.diff(tree))

        workspace.apply_patch(tree, task.test_patch, label="test.patch")

        with tempfile.TemporaryDirectory(prefix="harness-out-") as out:
            parsed = run_tests(
                tree, task, out_dir=Path(out), image=image, timeout=timeout
            )

    return _verdict(
        task,
        parsed,
        stripped=stripped,
        sensitive=sensitive,
        patch_loc=patch_loc,
        reference_loc=reference_loc,
        is_baseline=is_baseline,
    )


def _has_solution(task: Task) -> bool:
    return (task.dir / "solution.patch").exists()


def _changed_paths(tree: Path) -> list[str]:
    return [path for _, path in workspace._status_entries(tree)]


def _verdict(
    task: Task,
    parsed: ParsedRun,
    *,
    stripped: list[str] | None = None,
    sensitive: list[str] | None = None,
    patch_loc: int = 0,
    reference_loc: int = 0,
    is_baseline: bool = False,
) -> GradeResult:
    f2p = {t: parsed.status_of(t) for t in task.fail_to_pass}
    p2p = {t: parsed.status_of(t) for t in task.pass_to_pass}

    result = GradeResult(
        task_id=task.task_id,
        resolved=False,
        status=parsed.status,
        fail_to_pass=f2p,
        pass_to_pass=p2p,
        detail=parsed.detail,
        patch_loc=patch_loc,
        reference_loc=reference_loc,
        stripped_paths=stripped or [],
        sensitive_paths=sensitive or [],
    )

    # An untrustworthy run yields no verdict on its own. The caller retries; a
    # surviving error is scored as a failure, with the retry count as the audit
    # trail for whether the harness is to blame.
    if not parsed.trustworthy:
        result.outcome = Outcome.HARNESS_ERROR
        return result

    _reclassify(result, is_baseline=is_baseline)
    return result


def _reclassify(result: GradeResult, *, is_baseline: bool | None = None) -> None:
    """Derive `resolved` and `outcome` from the current test statuses.

    Split out so it can run again after flaky-test reclassification without
    duplicating the precedence rules.
    """
    if is_baseline is None:
        is_baseline = result.outcome is Outcome.BASELINE
    result.resolved = result.all_fail_to_pass_passed and result.all_pass_to_pass_passed

    if is_baseline:
        result.outcome = Outcome.BASELINE
    elif result.resolved:
        result.outcome = Outcome.RESOLVED
    elif result.all_fail_to_pass_passed:
        # Target bug fixed, but something else broke. The most interesting
        # failure, and invisible if only `resolved` is recorded.
        result.outcome = Outcome.REGRESSION
    else:
        result.outcome = Outcome.TESTS_FAILED
