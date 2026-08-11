# TypeError when using defer() on a related manager inheriting FETCH_PEERS mode

Using a related manager (e.g. `author.books`) inheriting a fetch mode of `FETCH_PEERS` from its origin instance, and then chaining `defer()`, gives a `TypeError` when trying to fetch that instance.

[https://dryorm.xterm.info/fetch-modes-bug-repro dryorm snippet]
```py
from django.db import models

class Author(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Book(models.Model):
    author = models.ForeignKey(
        Author, models.CASCADE, related_name="books"
    )
    editor = models.ForeignKey(
        Author, models.CASCADE, null=True, related_name="edited_books"
    )

def run():
    plato = Author.objects.create(name='Plato')
    dialogue1 = Book.objects.create(author=plato)
    dialogue2 = Book.objects.create(author=plato)
    for author in Author.objects.fetch_mode(models.FETCH_PEERS):
        break
    for book in author.books.defer("editor"):
        print(book.editor)
```
```py
Traceback (most recent call last):
  File "/django-pr/django/db/models/fields/related_descriptors.py", line 250, in __get__
    rel_obj = self.field.get_cached_value(instance)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/fields/mixins.py", line 21, in get_cached_value
    return instance._state.fields_cache[self.cache_name]
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^
KeyError: 'editor'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/django-pr/django/db/models/fields/__init__.py", line 2197, in get_prep_value
    return int(value)
           ^^^^^^^^^^
TypeError: int() argument must be a string, a bytes-like object or a real number, not 'tuple'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/app/./manage.py", line 36, in <module>
    execute_from_command_line(sys.argv)
  File "/django-pr/django/core/management/__init__.py", line 443, in execute_from_command_line
    utility.execute()
  File "/django-pr/django/core/management/__init__.py", line 437, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File "/django-pr/django/core/management/base.py", line 422, in run_from_argv
    self.execute(*args, **cmd_options)
  File "/django-pr/django/core/management/base.py", line 466, in execute
    output = self.handle(*args, **options)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/app/management/commands/execute.py", line 292, in handle
    returned = models.run()
               ^^^^^^^^^^^^
  File "/app/app/models.py", line 24, in run
    print(book.editor)
          ^^^^^^^^^^^
  File "/django-pr/django/db/models/fields/related_descriptors.py", line 266, in __get__
    instance._state.fetch_mode.fetch(self, instance)
  File "/django-pr/django/db/models/fetch_modes.py", line 38, in fetch
    fetcher.fetch_many(instances)
  File "/django-pr/django/db/models/fields/related_descriptors.py", line 291, in fetch_many
    prefetch_related_objects(missing_instances, self.field.name)
  File "/django-pr/django/db/models/query.py", line 2683, in prefetch_related_objects
    obj_list, additional_lookups = prefetch_one_level(
                                   ^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/query.py", line 2858, in prefetch_one_level
    all_related_objects = list(rel_qs)
                          ^^^^^^^^^^^^
  File "/django-pr/django/db/models/query.py", line 432, in __iter__
    self._fetch_all()
  File "/django-pr/django/db/models/query.py", line 2229, in _fetch_all
    self._result_cache = list(self._iterable_class(self))
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/query.py", line 96, in __iter__
    results = compiler.execute_sql(
              ^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/sql/compiler.py", line 1611, in execute_sql
    sql, params = self.as_sql()
                  ^^^^^^^^^^^^^
  File "/django-pr/django/db/models/sql/compiler.py", line 795, in as_sql
    self.compile(self.where) if self.where is not None else ("", [])
    ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/sql/compiler.py", line 578, in compile
    sql, params = node.as_sql(self, self.connection)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/sql/where.py", line 151, in as_sql
    sql, params = compiler.compile(child)
                  ^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/sql/compiler.py", line 578, in compile
    sql, params = node.as_sql(self, self.connection)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/fields/tuple_lookups.py", line 148, in as_sql
    return super().as_sql(compiler, connection)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/lookups.py", line 551, in as_sql
    return super().as_sql(compiler, connection)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/lookups.py", line 239, in as_sql
    rhs_sql, rhs_params = self.process_rhs(compiler, connection)
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/fields/tuple_lookups.py", line 371, in process_rhs
    return compiler.compile(Tuple(*result))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/sql/compiler.py", line 576, in compile
    sql, params = vendor_impl(self, self.connection)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/fields/tuple_lookups.py", line 46, in as_sqlite
    return self.as_sql(compiler, connection)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/expressions.py", line 1111, in as_sql
    arg_sql, arg_params = compiler.compile(arg)
                          ^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/sql/compiler.py", line 576, in compile
    sql, params = vendor_impl(self, self.connection)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/fields/tuple_lookups.py", line 46, in as_sqlite
    return self.as_sql(compiler, connection)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/expressions.py", line 1111, in as_sql
    arg_sql, arg_params = compiler.compile(arg)
                          ^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/sql/compiler.py", line 576, in compile
    sql, params = vendor_impl(self, self.connection)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/expressions.py", line 1194, in as_sqlite
    sql, params = self.as_sql(compiler, connection, **extra_context)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/expressions.py", line 1179, in as_sql
    val = output_field.get_db_prep_value(val, connection=connection)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/fields/__init__.py", line 2888, in get_db_prep_value
    return value if prepared else self.get_prep_value(value)
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/django-pr/django/db/models/fields/__init__.py", line 2199, in get_prep_value
    raise e.__class__(
TypeError: Field 'id' expected a number but got (None,).
```

Reported in django ticket #37036: https://code.djangoproject.com/ticket/37036
