# InlineAdmin breaks when using db_default on primary key field without a python default

Using db_default with the new UUID4 and UUID7 functions crashes in the admin. Model defined with `models.UUIDField` as primary key with `db_default`
e.g.
```python
uuid = models.UUIDField(primary_key=True, db_default=UUID7(), editable=False, verbose_name="UUID")
```
crashes when opening "add" page in the admin:
```
ValidationError at /admin/someapp/somemodel/add/
['“<django.db.models.expressions.DatabaseDefault object at 0x7e81f7b76e40>” is not a valid UUID.']
```
```
Traceback (most recent call last):
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/fields/__init__.py", line 2856, in to_python
    return uuid.UUID(**{input_form: value})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.14/uuid.py", line 216, in __init__
    hex = hex.replace('urn:', '').replace('uuid:', '')
          ^^^^^^^^^^^

During handling of the above exception ('DatabaseDefault' object has no attribute 'replace'), another exception occurred:
  File "/app/.venv/lib/python3.14/site-packages/django/core/handlers/exception.py", line 56, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/core/handlers/base.py", line 199, in _get_response
    response = wrapped_callback(request, *callback_args, **callback_kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/contrib/admin/options.py", line 770, in wrapper
    return self.admin_site.admin_view(view)(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/utils/decorators.py", line 191, in _view_wrapper
    result = _process_exception(request, e)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/utils/decorators.py", line 189, in _view_wrapper
    response = view_func(request, *args, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/views/decorators/cache.py", line 79, in _view_wrapper
    response = view_func(request, *args, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/contrib/admin/sites.py", line 248, in inner
    return view(request, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/contrib/admin/options.py", line 2225, in add_view
    return self.changeform_view(request, None, form_url, extra_context)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/utils/decorators.py", line 47, in _wrapper
    return bound_method(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/utils/decorators.py", line 191, in _view_wrapper
    result = _process_exception(request, e)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/utils/decorators.py", line 189, in _view_wrapper
    response = view_func(request, *args, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/contrib/admin/options.py", line 2039, in changeform_view
    return self._changeform_view(request, object_id, form_url, extra_context)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/contrib/admin/options.py", line 2145, in _changeform_view
    formsets, inline_instances = self._create_formsets(
                                 
  File "/app/.venv/lib/python3.14/site-packages/django/contrib/admin/options.py", line 2645, in _create_formsets
    formset = FormSet(**formset_params)
              ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/forms/models.py", line 1132, in __init__
    qs = queryset.filter(**{self.fk.name: self.instance})
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/query.py", line 1653, in filter
    return self._filter_or_exclude(False, args, kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/query.py", line 1671, in _filter_or_exclude
    clone._filter_or_exclude_inplace(negate, args, kwargs)
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/query.py", line 1681, in _filter_or_exclude_inplace
    self._query.add_q(Q(*args, **kwargs))
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/sql/query.py", line 1680, in add_q
    clause, _ = self._add_q(q_object, can_reuse)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/sql/query.py", line 1712, in _add_q
    child_clause, needed_inner = self.build_filter(
                                 
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/sql/query.py", line 1612, in build_filter
    condition = self.build_lookup(lookups, col, value)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/sql/query.py", line 1439, in build_lookup
    lookup = lookup_class(lhs, rhs)
             ^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/lookups.py", line 35, in __init__
    self.rhs = self.get_prep_lookup()
               ^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/fields/related_lookups.py", line 113, in get_prep_lookup
    self.rhs = target_field.get_prep_value(self.rhs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/fields/__init__.py", line 2840, in get_prep_value
    return self.to_python(value)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/app/.venv/lib/python3.14/site-packages/django/db/models/fields/__init__.py", line 2858, in to_python
    raise exceptions.ValidationError(
    ^
```
As far as I'm aware this a bug in a new feature, or maybe I did something wrong 🤔

Reported in django ticket #37139: https://code.djangoproject.com/ticket/37139
