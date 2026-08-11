# KeyError when adding new objects two relations deep via inlines but the intermediate model is not registered with the admin

With these models:
```py
class Analysis(models.Model): ...

class Song(models.Model):
    users = models.ManyToManyField("auth.User")
    analysis = models.ForeignKey("Analysis", on_delete=models.CASCADE, null=True)
```
And these admins:
```py
class SongInline(admin.TabularInline):
    model = Song


class AnalysisAdmin(admin.ModelAdmin):
    inlines = [SongInline]

admin.site.register([Analysis], AnalysisAdmin)
```
1. Admin: Analysis: Add
2. Click the "+" in the Users column of the Songs inline
3. Fill out the field
4. Notice `Song` is in the URL as the `source_model` arg. This will be a problem, since `Song` is not registered with the admin.
5. Submit

```py
  File "/Users/jacobwalls/django/django/contrib/admin/options.py", line 711, in wrapper
    return self.admin_site.admin_view(view)(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/utils/decorators.py", line 191, in _view_wrapper
    result = _process_exception(request, e)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/utils/decorators.py", line 189, in _view_wrapper
    response = view_func(request, *args, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/views/decorators/cache.py", line 79, in _view_wrapper
    response = view_func(request, *args, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/contrib/admin/sites.py", line 247, in inner
    return view(request, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/utils/decorators.py", line 47, in _wrapper
    return bound_method(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/views/decorators/debug.py", line 142, in sensitive_post_parameters_wrapper
    return view(request, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/utils/decorators.py", line 191, in _view_wrapper
    result = _process_exception(request, e)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/utils/decorators.py", line 189, in _view_wrapper
    response = view_func(request, *args, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/contrib/auth/admin.py", line 119, in add_view
    return self._add_view(request, form_url, extra_context)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/contrib/auth/admin.py", line 147, in _add_view
    return super().add_view(request, form_url, extra_context)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/contrib/admin/options.py", line 1984, in add_view
    return self.changeform_view(request, None, form_url, extra_context)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/utils/decorators.py", line 47, in _wrapper
    return bound_method(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/utils/decorators.py", line 191, in _view_wrapper
    result = _process_exception(request, e)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/utils/decorators.py", line 189, in _view_wrapper
    response = view_func(request, *args, **kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/contrib/admin/options.py", line 1842, in changeform_view
    return self._changeform_view(request, object_id, form_url, extra_context)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/contrib/admin/options.py", line 1900, in _changeform_view
    return self.response_add(request, new_object)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/contrib/auth/admin.py", line 251, in response_add
    return super().response_add(request, obj, post_url_continue)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/jacobwalls/django/django/contrib/admin/options.py", line 1431, in response_add
    source_admin = self.admin_site._registry[source_model]
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Exception Type: KeyError at /admin/auth/user/add/
Exception Value: <class 'earTrain.models.Song'>
```
Regression in b1ffa9a9d78b0c2c5ad6ed5a1d84e380d5cfd010.

Reported in django ticket #36921: https://code.djangoproject.com/ticket/36921
