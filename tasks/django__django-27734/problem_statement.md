# Parallel test workers can be assigned an unexpected index when recovering from errors

I've had this problem since upgrading to Python 3.6 on macOS Sierra – when I run my tests in parallel many of them blow up trying to use database with index that is higher than the number of parallel test processes. On my MacBook the default process number is 4 and tests fail trying to connect to test_my_db_5. On my iMac the default process number is 8 and test fail connecting to test_my_db_9. The same thing happens if I set the number of processes explicitly, e.g. `--parallel=2`. Higher number of processes yields less failures. If I explicitly set the number of processes to a number that is greater than the number of my test files then the tests succeed.



```
Traceback (most recent call last):
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/test/testcases.py", line 216, in __call__
    self._post_teardown()
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/test/testcases.py", line 908, in _post_teardown
    self._fixture_teardown()
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/test/testcases.py", line 943, in _fixture_teardown
    inhibit_post_migrate=inhibit_post_migrate)
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/core/management/__init__.py", line 130, in call_command
    return command.execute(*args, **defaults)
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/core/management/base.py", line 345, in execute
    output = self.handle(*args, **options)
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/core/management/commands/flush.py", line 54, in handle
    allow_cascade=allow_cascade)
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/core/management/sql.py", line 15, in sql_flush
    tables = connection.introspection.django_table_names(only_existing=True, include_views=False)
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/db/backends/base/introspection.py", line 88, in django_table_names
    existing_tables = self.table_names(include_views=include_views)
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/db/backends/base/introspection.py", line 55, in table_names
    with self.connection.cursor() as cursor:
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/db/backends/base/base.py", line 233, in cursor
    cursor = self.make_cursor(self._cursor())
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/db/backends/base/base.py", line 204, in _cursor
    self.ensure_connection()
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/db/backends/base/base.py", line 199, in ensure_connection
    self.connect()
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/db/utils.py", line 94, in __exit__
    six.reraise(dj_exc_type, dj_exc_value, traceback)
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/utils/six.py", line 685, in reraise
    raise value.with_traceback(tb)
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/db/backends/base/base.py", line 199, in ensure_connection
    self.connect()
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/db/backends/base/base.py", line 171, in connect
    self.connection = self.get_new_connection(conn_params)
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/django/db/backends/postgresql/base.py", line 176, in get_new_connection
    connection = Database.connect(**conn_params)
  File "/Users/amw/.virtualenvs/envname/lib/python3.6/site-packages/psycopg2/__init__.py", line 164, in connect
    conn = _connect(dsn, connection_factory=connection_factory, async=async)
django.db.utils.OperationalError: FATAL:  database "test_my_db_5" does not exist

```
My requirements.txt file:
```
boto3==1.4.3
daemonize==2.4.7
Django==1.10.5
django-appconf==1.0.2
django-compressor==2.1
django-debug-toolbar==1.6
django-dotenv==1.4.1
django-extensions==1.7.5
django-ipware==1.1.6
djangorestframework==3.5.3
filemagic==1.6
inflection==0.3.1
jmespath==0.9.0
psycopg2==2.6.2
python-dateutil==2.6.0
rcssmin==1.0.6
rjsmin==1.0.12
s3transfer==0.1.10
six==1.10.0
sqlparse==0.2.2
uWSGI==2.0.14
```

Reported in django ticket #27734: https://code.djangoproject.com/ticket/27734
