# ModelAdmin.list_display: AttributeError when a __ lookup path ends in a relation field (regression from #36926)

Since #36926, `list_display` entries using `__` lookup syntax to traverse related fields (documented at https://docs.djangoproject.com/en/dev/ref/contrib/admin/#django.contrib.admin.ModelAdmin.list_display) raise `AttributeError` when the *final* segment of the path is itself a relation field (ForeignKey/OneToOneField), rather than a scalar field.

This worked correctly before #36926 and is not limited to any unusual setup — any `related__fk_field` entry regresses.

=== Minimal reproduction ===

```python
class Publisher(models.Model):
    name = models.CharField(max_length=100)

class Book(models.Model):
    title = models.CharField(max_length=100)
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)

class Author(models.Model):
    name = models.CharField(max_length=100)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["name", "book__publisher"]
```
Visiting the `Author` changelist with at least one row raises:

```
AttributeError: 'Author' object has no attribute 'publisher'
```
=== Root cause ===

#36926 added this to `lookup_field()` in `django/contrib/admin/utils.py`,
specifically to let `display_for_field()` recognize `BooleanField`s reached
via a `__` path so it can render the boolean icon:

```python
                    # The final field is needed for displaying boolean icons.
                    if LOOKUP_SEP in name:
                        f = get_fields_from_path(opts.model, name)[-1]
```
This sets `f` unconditionally whenever the path contains `LOOKUP_SEP`, not only when the terminal field is a `BooleanField`. Previously, `f` stayed
`None` for this whole branch (the "method, property, related field, or callable" fallback), and `items_for_result()` in `django/contrib/admin/templatetags/admin_list.py` used the already correctly-traversed `value` via `display_for_value()`.

Now that `f` is non-`None`, `items_for_result()` takes a different branch that assumes `f` is a field belonging to `result` directly:

```python
            else:
                if isinstance(f.remote_field, models.ManyToOneRel):
                    field_val = getattr(result, f.name)
```
That assumption holds for the normal case (`list_display = ["publisher"]` where `publisher` really is a field on the model being rendered), but not for the `__`-traversal case, where `f` is a field on the *related* model several hops down the path — `result` (an `Author`) has no `publisher` attribute; `result.book` does.

=== Suggested fix direction ===

Scope the new `f` assignment to its stated purpose — only set it when the terminal field is actually a `BooleanField` — rather than for every `LOOKUP_SEP`-containing path:

```python
                    if LOOKUP_SEP in name:
                        final_field = get_fields_from_path(opts.model, name)[-1]
                        if isinstance(final_field, models.BooleanField):
                            f = final_field
```
This preserves the boolean-icon feature #36926 added while restoring the pre-6.1 (and documented) behavior for `__` paths ending in any other field
type, including relations.

I have not attempted a full patch/tests — that's a little out of my league I'm afraid.

Reported in django ticket #37230: https://code.djangoproject.com/ticket/37230
