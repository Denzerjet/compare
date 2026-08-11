# Deprecation warnings skip past packages named "django_*"

The `django_file_prefixes()` utility doesn't include a trailing path separator, so also matches other packages whose installation directories start with "django". As a result, use of deprecated features in those packages will be mis-attributed to some other code outside those packages.

Django's implementation frequently has code like this:

```python
# django.some_module

import warnings
from django.utils.deprecation import RemovedInDjangoXXWarning, django_file_prefixes

def _some_helper():
    ...
    warnings.warn(
        "This is deprecated.",
        RemovedInDjangoXXWarning,
        skip_file_prefixes=django_file_prefixes(),
    )

def some_django_feature():
    ...
    _some_helper()
    ...
```
The intent is a caller to `some_django_feature()` outside Django gets a deprecation warning pointed at their own code. (Not pointing at the call to `_some_helper()` in Django's implementation.)

As [https://github.com/django/django/blob/8ee73415270a1a54daaec9bb529ad82c6f7a6d4c/django/utils/deprecation.py#L13-L18 currently implemented], `django_file_prefixes()` returns the directory where Django is installed (in a tuple). E.g., `("/venv/site-packages/django",)`.

If `some_django_feature()` is called from a (hypothetical) `django_goodies` package installed in `/venv/site-packages/django_goodies/__init__.py`, the warning will skip it too: that filename [https://docs.python.org/3/library/stdtypes.html#str.startswith startswith] the django_file_prefixes. The resulting warning will point to the first stack frame outside `django_goodies`, which may be completely disconnected from the deprecated feature usage.

Reported in django ticket #37067: https://code.djangoproject.com/ticket/37067
