# Running tests on SQLite with --parallel (using spawn) does not respect DATABASES["TEST"]["NAME"]

When running unit tests on SQLite on macOS with the `--parallel` [https://docs.djangoproject.com/en/6.0/ref/django-admin/#cmdoption-test-parallel flag] and the `DATABASES["TEST"]["NAME"]` [https://docs.djangoproject.com/en/6.0/ref/settings/#std-setting-TEST_NAME setting] set (e.g. to `mytests.db`), the tests fail to run because SQLite tries to connect to databases named `default_*.sqlite3` instead of the cloned `mytests_*.db`.

You can replicate this with the Django test suite itself, e.g. with the following change:

_[a proposed patch was removed from this report]_
and then run a subset of the tests, e.g.

```shell
DATABASE_NAME=django.db ./runtests.py --verbosity=2 --parallel=2 -- model_fields
```
You'll get a bunch of errors like the following:

```shell
Traceback (most recent call last):
  File "/../python/3.14.2/lib/python3.14/multiprocessing/process.py", line 320, in _bootstrap
    self.run()
    ~~~~~~~~^^
  File "/../python/3.14.2/lib/python3.14/multiprocessing/process.py", line 108, in run
    self._target(*self._args, **self._kwargs)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/../python/3.14.2/lib/python3.14/multiprocessing/pool.py", line 109, in worker
    initializer(*initargs)
    ~~~~~~~~~~~^^^^^^^^^^^
  File "/django/django/test/runner.py", line 479, in _safe_init_worker
    init_worker(counter, *args, **kwargs)
    ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django/django/test/runner.py", line 464, in _init_worker
    connection.creation.setup_worker_connection(_worker_id)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "/django/django/db/backends/sqlite3/creation.py", line 145, in setup_worker_connection
    source_db = self.connection.Database.connect(
        f"file:{alias}_{_worker_id}.sqlite3?mode=ro", uri=True
    )
sqlite3.OperationalError: unable to open database file
```
but you can see that Django successfully created/destroyed the test databases with the correct names:

```shell
Cloning test database for alias 'default' ('django.db')...
Cloning test database for alias 'default' ('django.db')...

# test results go here

Destroying test database for alias 'default' ('django_1.db')...
Destroying test database for alias 'default' ('django_2.db')...
Destroying test database for alias 'default' ('django.db')...
```
This also affects a multi-database setup if you set the `["TEST"]["NAME"]` for that database. With the above example, if you run the `multiple_database` test suite (instead of `model_fields`), you won't see any errors for the `other` database; as Django will create and connect to the fallback test name based on the alias, i.e. `other_*.sqlite3`. However, if you also add `DATABASES["other"]["TEST"] = {"NAME": "other_" + DATABASE_NAME}` to the settings changes in the above example, the same error now also happens for the `other` database.

This prevents the use of custom names for running tests with `--parallel` > 1 (or `auto`), which can be particularly useful when you want to use `--keepdb` with different names. With `--parallel=1`, this issue does not occur.

I believe it is because despite the cloning was done correctly using the given test database file name in [https://github.com/django/django/blob/2de474dffca008038a7f9fe10289f390c5f4f15b/django/db/backends/sqlite3/creation.py#L58-L60 get_test_db_clone_settings], the logic in [https://github.com/django/django/blob/2de474dffca008038a7f9fe10289f390c5f4f15b/django/db/backends/sqlite3/creation.py#L145-L147 setup_worker_connection] does not use the clone db names (it always uses `{alias}_{_worker_id}.sqlite3` instead) when copying them over to the in-memory database.

FWIW, I encountered this while trying to run [https://github.com/wagtail/wagtail/pull/13922 Wagtail's test suite] in parallel with `--keepdb`. I can give a smaller reproducible example if necessary, but I think the example with Django's own test suite can be a good example too.

Reported in django ticket #36946: https://code.djangoproject.com/ticket/36946
