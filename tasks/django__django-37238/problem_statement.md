# save() falls back to python default even when DatabaseDefault instance is assigned

When saving an object whose primary key is a `OneToOneField`, and when that value is meant to come from an unsaved related object, and when that related object uses `db_default`, a2348c85fc6c20087935c74cd99340dd4ef2dcdc has the unintentional effect of falling back to the field's `default` instead of getting it from the related object once saved. EDIT: before 6.1, the fallback was to the related object's db_default expression, which isn't quite right either, so my current proposal is to just match the 6.0 behavior and then bounce the rest to a follow-up issue.

To demonstrate, adjust a test being drafted in this [https://github.com/django/django/pull/21677 other PR] (where the `bulk_create()` case was considered and handled) to use `save()` instead:

Passes before a2348c85fc6c20087935c74cd99340dd4ef2dcdc on SQLite. Other databases have other behaviors, like raising integrity errors, so we might need some test skips here. This should be rewritten to use Now() instead of a constant value; I found the constant value was easier to debug.

_[a proposed patch was removed from this report]_
```py
======================================================================
FAIL: test_pk_from_related_instance_saved_after_init_with_defaults (bulk_create.tests.BulkCreateTests.test_pk_from_related_instance_saved_after_init_with_defaults)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/jwalls/django/tests/bulk_create/tests.py", line 455, in test_pk_from_related_instance_saved_after_init_with_defaults
    self.assertEqual(obj.pk, related_object.pk)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 1 != 42

----------------------------------------------------------------------
Ran 1 test in 0.007s

FAILED (failures=1)
```

Reported in django ticket #37238: https://code.djangoproject.com/ticket/37238
