"""Proves the grading path is trustworthy, using one hand-written fixture task.

This is the gate for step 1 of the build order. Everything downstream -- mining,
validation, the model comparison itself -- inherits whatever correctness this
file establishes, so it asserts the properties grading is *relied on* to have
rather than merely exercising the code.

Run:  ./.venv/bin/python -m unittest discover -s tests -v
Needs a running docker daemon, the harness image built, and repo/django cloned.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from harness.env import workspace  # noqa: E402
from harness.grade import Outcome, diff_loc, grade  # noqa: E402
from harness.grade.parse import PASSING, RunStatus  # noqa: E402
from harness.schema import Task  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "django__django-37198"
TARGET = "utils_tests.test_http.ContentDispositionHeaderTests.test_basic"


class GradingContractTests(unittest.TestCase):
    """The three criteria validate.py will enforce on every mined task."""

    @classmethod
    def setUpClass(cls):
        cls.task = Task.load(FIXTURE)
        # Graded states are expensive (a container each), so compute them once
        # and assert against them repeatedly.
        cls.pre = grade(cls.task)                                # tests only
        cls.post = grade(cls.task, cls.task.solution_patch)      # tests + fix

    # -- criterion 1: the task is genuinely unsolved before the fix -----------

    def test_pre_patch_run_is_trustworthy(self):
        self.assertIs(self.pre.status, RunStatus.OK, self.pre.detail)

    def test_pre_patch_fail_to_pass_fails(self):
        self.assertEqual(self.pre.fail_to_pass[TARGET], "failed")
        self.assertFalse(self.pre.all_fail_to_pass_passed)

    def test_pre_patch_pass_to_pass_all_pass(self):
        # If any of these fail before the fix, the task's baseline is broken and
        # a regression check after the fix would be meaningless.
        bad = {t: s for t, s in self.pre.pass_to_pass.items() if s not in PASSING}
        self.assertEqual(bad, {})

    def test_pre_patch_is_not_resolved(self):
        self.assertFalse(self.pre.resolved)

    # -- criterion 2: the reference fix solves it ----------------------------

    def test_post_patch_run_is_trustworthy(self):
        self.assertIs(self.post.status, RunStatus.OK, self.post.detail)

    def test_post_patch_resolves(self):
        self.assertTrue(self.post.resolved, self.post.detail)

    def test_post_patch_has_no_regressions(self):
        self.assertEqual(self.post.regressions, [])

    # -- the grader's own guarantees -----------------------------------------

    def test_no_test_is_silently_missing(self):
        """A test that never ran must not be mistaken for one that passed."""
        for state in (self.pre, self.post):
            statuses = {**state.fail_to_pass, **state.pass_to_pass}
            self.assertNotIn("missing", statuses.values())

    def test_subtest_failure_is_attributed_to_its_method(self):
        """The property text parsing cannot deliver.

        The fixture's failure surfaces only on subtest lines whose printed ids
        carry parameter suffixes, while the enclosing method's status line is
        left blank. Grading must still pin the failure to the method id named in
        fail_to_pass.
        """
        # "failed" rather than "missing" is the whole assertion: the method id
        # was located and given the verdict its subtests earned.
        self.assertEqual(self.pre.fail_to_pass[TARGET], "failed")

    def test_tests_are_immune_to_the_candidate_patch(self):
        """A patch that rewrites the tests must not be able to buy a pass."""
        sabotage = _read_patch("sabotage_tests.patch")
        result = grade(self.task, sabotage)
        self.assertIs(result.status, RunStatus.OK, result.detail)
        self.assertFalse(
            result.resolved,
            "a patch that deletes the failing assertions was graded as resolved",
        )

    def test_shadowing_the_grading_machinery_is_stripped(self):
        """A patch cannot plant a module that impersonates the collector.

        /testbed/tests is sys.path[0] and /testbed precedes /harness on
        PYTHONPATH, so a root-level harness_settings.py would win the import and
        could forge a clean results.json without running a single test. Verified
        exploitable before the whitelist existed, hence this test.
        """
        result = grade(self.task, _read_patch("shadow_settings.patch"))
        self.assertIn("harness_settings.py", result.stripped_paths)
        self.assertFalse(result.resolved, "forged results were accepted")
        # The forgery is not merely ineffective -- real tests must have run.
        self.assertIs(result.status, RunStatus.OK, result.detail)
        self.assertEqual(result.fail_to_pass[TARGET], "failed")

    def test_only_whitelisted_paths_survive(self):
        """Changes under django/ are kept; everything else is reverted."""
        result = grade(self.task, _read_patch("shadow_settings.patch"))
        self.assertEqual(result.stripped_paths, ["harness_settings.py"])

    def test_unapplyable_patch_is_unresolved_not_an_error(self):
        """Garbage output is a model failure, not harness breakage."""
        result = grade(self.task, "not a diff at all\n")
        self.assertFalse(result.resolved)
        self.assertIs(result.status, RunStatus.OK)

    def test_grading_is_reproducible(self):
        """The same (task, patch) must yield the same verdict.

        This is no longer a per-task validation criterion -- validation is two
        runs, and an identical re-run cannot detect order dependence anyway
        (unittest order is deterministic). It is asserted here because the
        property is now supplied by the *environment*: PYTHONHASHSEED=0 in the
        image pins set-iteration order, which is what makes a verdict a pure
        function of its inputs. If that env var were dropped from the Dockerfile,
        this is the test that should fail.
        """
        repeat = grade(self.task, self.task.solution_patch)
        self.assertTrue(repeat.resolved)
        self.assertEqual(repeat.fail_to_pass, self.post.fail_to_pass)
        self.assertEqual(repeat.pass_to_pass, self.post.pass_to_pass)

    def test_hash_seed_is_pinned_in_the_image(self):
        """Guards the mechanism the test above depends on."""
        proc = subprocess.run(
            ["docker", "run", "--rm", self.task.env_image,
             "python", "-c", "import os; print(os.environ.get('PYTHONHASHSEED'))"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(proc.stdout.strip(), "0")

    def test_outcome_taxonomy(self):
        """A bare resolved=False flattens distinct failures into one bucket."""
        cases = [
            (None, Outcome.BASELINE),
            ("   \n  ", Outcome.NO_PATCH),
            ("not a diff at all\n", Outcome.UNAPPLYABLE),
            (self.task.solution_patch, Outcome.RESOLVED),
        ]
        for patch, expected in cases:
            with self.subTest(outcome=expected.value):
                self.assertIs(grade(self.task, patch).outcome, expected)

    def test_loc_is_measured_identically_for_model_and_reference(self):
        """A ratio between two differently-computed numbers means nothing."""
        self.assertEqual(self.post.reference_loc, diff_loc(self.task.solution_patch))
        # The reference fix graded against itself must come out at exactly 1.0.
        self.assertEqual(self.post.patch_loc, self.post.reference_loc)
        self.assertEqual(self.post.loc_ratio, 1.0)

    def test_empty_patch_is_not_scored_as_surgical(self):
        """no_patch must not read as LOC 0 = admirably minimal."""
        result = grade(self.task, "")
        self.assertIs(result.outcome, Outcome.NO_PATCH)
        self.assertEqual(result.patch_loc, 0)
        self.assertFalse(result.resolved)


class WorkspaceTests(unittest.TestCase):
    def test_worktree_is_pinned_and_cleaned_up(self):
        task = Task.load(FIXTURE)
        with workspace.worktree(task.base_commit) as tree:
            self.assertTrue((tree / "django" / "utils" / "http.py").exists())
            path = tree
        self.assertFalse(path.exists(), "worktree outlived its context manager")

    def test_diff_is_empty_on_a_clean_worktree(self):
        task = Task.load(FIXTURE)
        with workspace.worktree(task.base_commit) as tree:
            self.assertEqual(workspace.diff(tree), "")


def _read_patch(name: str) -> str:
    return (FIXTURE / name).read_text()


if __name__ == "__main__":
    unittest.main(verbosity=2)
