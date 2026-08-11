# task_finished signal logs "NoneType: None" when no exception is raised

The test provided on [https://github.com/django/django/pull/20722 PR #20722] demonstrates that faux exceptions are logged as `NoneType: None` by the `log_task_finished` signal handler:

```py
======================================================================
FAIL: test_successful_task_no_none_type_in_logs (tasks.test_immediate_backend.ImmediateBackendTestCase.test_successful_task_no_none_type_in_logs)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/jwalls/django/tests/tasks/test_immediate_backend.py", line 238, in test_successful_task_no_none_type_in_logs
    self.assertNotIn("NoneType", log_output)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'NoneType' unexpectedly found in 'INFO:django.tasks:Task id=1yKnLbcmTGMEUfj0B1JG0766LDM1Sono path=tasks.tasks.noop_task state=SUCCESSFUL\nNoneType: None'

----------------------------------------------------------------------
```

Reported in django ticket #36951: https://code.djangoproject.com/ticket/36951
