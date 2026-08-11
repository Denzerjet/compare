# Empty form for inlines breaks when using db_default on primary key field

Using `db_default` with the new `UUID4` or `UUID7` functions breaks saving inlines. For example,

- `models.py`
```python
class MyMain(models.Model):
    uuid = models.UUIDField(primary_key=True, db_default=UUID7(), editable=False, verbose_name="UUID")
    name = models.CharField(max_length=100)

class MyChild(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(MyMain, models.DB_CASCADE)
```
- `admin.py`

```python
class ChildAdmin(admin.TabularInline):
    model = MyChild
    extra = 0


class MainAdmin(admin.ModelAdmin):
    inlines = [ChildAdmin]


admin.site.register(MyChild)
admin.site.register(MyMain, MainAdmin)
```
`DatabaseDefault` instances are rendered as values of the parent fields:

```
<tr class="form-row  empty-form" id="mychild_set-empty">
  <td class="original">      
     <input type="hidden" name="mychild_set-__prefix__-id" id="id_mychild_set-__prefix__-id">
     <input type="hidden" name="mychild_set-__prefix__-parent" value="&lt;django.db.models.expressions.DatabaseDefault object at 0x750a2aa14ad0&gt;" id="id_mychild_set-__prefix__-parent">
  </td>
  ...
```
which causes the following error when trying to save:
```
[{'parent': ['The inline value did not match the parent instance.']}]
```

Reported in django ticket #37147: https://code.djangoproject.com/ticket/37147
