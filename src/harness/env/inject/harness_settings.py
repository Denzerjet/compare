"""Settings module used for all grading runs.

Mounted read-only at /harness and selected with --settings=harness_settings.

Deliberately thin: it inherits django's own tests/test_sqlite.py so that the
database, hasher, and timezone configuration stay whatever upstream says they
should be at the task's commit, and adds only the TEST_RUNNER override that
installs the structured result collector. runtests.py falls back to
DiscoverRunner only when settings define no TEST_RUNNER, so setting it here is
enough to take over.

test_sqlite resolves because runtests.py is executed as /testbed/tests/
runtests.py, which puts /testbed/tests on sys.path as the script directory.
"""

from test_sqlite import *  # noqa: F401,F403

TEST_RUNNER = "harness_runner.HarnessRunner"
