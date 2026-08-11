# Deprecate and rename django.db.transaction.savepoint

I proposed this in https://github.com/django/new-features/issues/138 and it is now accepted.

Rename `savepoint` to `savepoint_create` and add a new `savepoint` function as a deprecated alias or wrapper for `savepoint_create`. Once the deprecation period has ended remove `savepoint`. This will free the name for use for a higher-level `savepoint` context manager.

Reported in django ticket #37045: https://code.djangoproject.com/ticket/37045
