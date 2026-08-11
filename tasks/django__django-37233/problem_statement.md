# Admin renders a sort control for every "__str__" column

Since ticket:10743#comment:26, any `__str__` column in an admin list view is rendered as a sortable column, regardless of whether it has been linked to a column and marked as sortable.
This simple model would reproduce it.
```python
# models.py
class SortingTest(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


# admin.py
admin.site.register(SortingTest)
```
list_display defaults to  `("__str__",)` but no sorting has been configured for the model's `__str__`, so the column should not be sortable.

`result_headers()` in `django/contrib/admin/templatetags/admin_list.py`
decides sortability with a substring test:

```python
if not admin_order_field and LOOKUP_SEP not in field_name:
    is_field_sortable = False
```
`LOOKUP_SEP` is `"__"` an so `__str__` flags as sortable

`ChangeList.get_ordering_field()` resolves the same name by attribute lookup
rather than by checking for double underscores, correctly finds no `admin_order_field`, and
`get_ordering()` drops it:

```python
order_field = self.get_ordering_field(field_name)
if not order_field:
    continue
```
Potentially result_headers could use get_ordering_field or some other technique.

This showed up reviewing ticket:27752#comment:16, which has the bigger issue that sorting on `__str__` doesn't work anyway. I don't judge this as a huge issue as once you need sorting you are most likely using specific list_dispaly values.

Reported in django ticket #37233: https://code.djangoproject.com/ticket/37233
