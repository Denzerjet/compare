"""Structured per-test result collection for the django test suite.

Mounted read-only at /harness inside the eval container and selected via
TEST_RUNNER in harness_settings.py.

Why this exists: the obvious way to grade is to run `runtests.py --verbosity 2`
and regex the "... ok / FAIL / ERROR" lines. That is unreliable in exactly the
cases this benchmark cares about. A test using subTest() prints its inline
status before its subtests are tallied, so a method with a failing subtest can
appear to pass on the status line and only show up in the trailing FAIL block
under a synthetic `[<subtest>]` id that does not match the method name in
fail_to_pass. Several of django's parameterised tests are written that way --
including the fixture task -- so text parsing would systematically misgrade
them.

Instead we hook unittest's TestResult, which is where the authoritative outcome
already lives, and emit JSON.

Outcomes are aggregated to the *method* id (`module.Class.method`), matching the
granularity of fail_to_pass / pass_to_pass in task.yaml. A method with any
failing subtest is `failed`.
"""

import json
import os
import unittest

from django.test.runner import DiscoverRunner

RESULT_PATH = os.environ.get("HARNESS_RESULT_PATH", "/harness_out/results.json")

# Higher wins when a single method reports more than once, which happens with
# subTest(): many passes plus one failure must aggregate to `failed`, never to
# `passed`. Ordering encodes "any bad news dominates good news".
_PRECEDENCE = {
    "passed": 0,
    "expected_failure": 1,
    "skipped": 2,
    "unexpected_success": 3,
    "failed": 4,
    "error": 5,
}


class HarnessResultMixin:
    """Records every outcome to a dict, then writes it out as JSON."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.harness_outcomes = {}

    def _record(self, test, status):
        try:
            test_id = test.id()
        except Exception:
            # A test that fails to even construct still needs to be visible
            # rather than silently dropped from the report.
            test_id = str(test)
        previous = self.harness_outcomes.get(test_id)
        if previous is None or _PRECEDENCE[status] > _PRECEDENCE[previous]:
            self.harness_outcomes[test_id] = status

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "unexpected_success")

    def addSubTest(self, test, subtest, outcome):
        super().addSubTest(test, subtest, outcome)
        # `test` is the parent TestCase, so test.id() is already the method id.
        # outcome is None on success, else an exc_info triple.
        if outcome is None:
            self._record(test, "passed")
        elif issubclass(outcome[0], test.failureException):
            self._record(test, "failed")
        else:
            self._record(test, "error")

    def stopTestRun(self):
        super().stopTestRun()
        self._write()

    def _write(self):
        os.makedirs(os.path.dirname(RESULT_PATH), exist_ok=True)
        payload = {
            # `complete` is the sentinel parse.py checks. Its absence means the
            # run died before finishing, which must never be read as "the
            # remaining tests passed".
            "complete": True,
            "outcomes": self.harness_outcomes,
            "totals": {
                "run": getattr(self, "testsRun", None),
                "failures": len(getattr(self, "failures", [])),
                "errors": len(getattr(self, "errors", [])),
                "skipped": len(getattr(self, "skipped", [])),
            },
        }
        with open(RESULT_PATH, "w") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)


class HarnessRunner(DiscoverRunner):
    """DiscoverRunner that swaps in the recording result class.

    Composed as a mixin over whatever result class DiscoverRunner would
    otherwise use, so --debug-sql and --pdb keep working.
    """

    def get_resultclass(self):
        base = super().get_resultclass() or unittest.TextTestResult
        return type("HarnessResult", (HarnessResultMixin, base), {})
