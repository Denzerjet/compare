# Readonly fields with db_default display DatabaseDefault representation

Readonly fields with `db_default` display `DatabaseDefault()` representation in the admin. For example:

- `models.py`
```python
class MyModel(models.Model):
    uuid = models.UUIDField(db_default=UUID7(), editable=False, primary_key=True)
    created_datetime = models.DateTimeField(db_default=Now(), editable=False)
    modified_datetime = models.DateTimeField(db_default=Now(), editable=False)
    name = models.TextField()
```
- `admin.py`

```python
@admin.register(MyModel)
class MyModelAdmin(admin.ModelAdmin):
    readonly_fields = ["uuid", "created_datetime", "modified_datetime"]
```
[[Image(Screenshot_20260613_125111.png​)]]
I think they should be consider as any other empty values.

Reported in django ticket #37168: https://code.djangoproject.com/ticket/37168
