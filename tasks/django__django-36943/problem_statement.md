# Autoreloader hides exceptions from urlconf module

Initialize an empty project
```
$ uv init . && uv add django && uv run django-admin startproject repro .

Initialized project `django-repro` at `/Users/amorton/src/django-repro`
Using CPython 3.14.0
Creating virtual environment at: .venv
Resolved 5 packages in 132ms
Installed 3 packages in 97ms
 + asgiref==3.11.1
 + django==6.0.2
 + sqlparse==0.5.5
```
Edit urls.py to the following:
```
from django.urls import include, path, register_converter


class MyConverter:
    # forgot to specify regex
    # regex = "[^/]+"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value


register_converter(MyConverter, "mine")

urlpatterns = [
    path("<mine:foo>", include([])),
]
```
Run the development server:
```
$ uv run manage.py runserver
Watching for file changes with StatReloader
Performing system checks...

Exception in thread django-main-thread:
Traceback (most recent call last):
   ...
  File "/Users/amorton/src/django-repro/repro/urls.py", line 15, in <module>
    register_converter(MyConverter, "mine")
    ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "/Users/amorton/src/django-repro/.venv/lib/python3.14/site-packages/django/urls/converters.py", line 57, in register_converter
    raise ValueError(f"Converter {type_name!r} is already registered.")
ValueError: Converter 'mine' is already registered.
```
What's going on here is that the original exception is being swallowed in django.utils.autoreload.BaseReloader.run.
The exception gets thrown after the call to register_converter succeeds, but before the URLResolver.urlconf_module cached property returns.
The urlconf module is executed a second time later, and the original exception is never shown to the user.

Ultimately this was a user-error on my part, but was very difficult to debug.

Reported in django ticket #36943: https://code.djangoproject.com/ticket/36943
