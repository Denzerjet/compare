# Migration using CreateModel with unique_together followed by AlterUniqueTogether crashes

Full project to reproduce: https://github.com/adamchainz/django-unique-together-bug

When squashing migrations I ended up with a migration that added a model with `unique_together`, then altered the unique_together later:

```
migrations.CreateModel(
    name="Book",
    fields=[
        (
            "id",
            models.AutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        ("title", models.CharField(default="", max_length=100)),
    ],
    options={"unique_together": {("title",)},},
),
# ...
migrations.AlterUniqueTogether(
    name="book", unique_together={("title", "author")},
),
```
This can crash when using `sqlmigrate` or `migrate` (see repo) with:

```
  File "/.../django/django/db/backends/base/schema.py", line 380, in alter_unique_together
    self._delete_composed_index(model, fields, {'unique': True}, self.sql_delete_unique)
  File "/.../django/django/db/backends/base/schema.py", line 414, in _delete_composed_index
    ", ".join(columns),
ValueError: Found wrong number (0) of constraints for testapp_book(title)
```
This is because `_delete_composed_index` from `AlterUniqueTogehter` tries to find the existing constraint name from the database.. But it hasn't been created yet, so it could never be found - its SQL is sitting in `deferred_sql`.

Reported in django ticket #31317: https://code.djangoproject.com/ticket/31317
