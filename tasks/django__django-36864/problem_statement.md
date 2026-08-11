# Add support for modules to import_string()

Adjust the test for customizing automatic shell imports to include a submodule of a module not normally imported, like `django.views.decorators`:

_[a proposed patch was removed from this report]_
This fails for the reason developed in #35402 that `import_string()` has trouble with modules: top-level modules always fail, and submodules sometimes succeed by happenstance. Here, `django.db.connection` only works as an automatic import because we depend on coincidentally importing `django.db` when running management commands (by importing `django.core.checks`). This seems fragile.

```py
AssertionError: '1 object could not be automatically imported:\n\n [62 chars]lly.' != '1 object imported automatically:\n\n  from django.[24 chars]gzip'
- 1 object could not be automatically imported:
+ 1 object imported automatically:
  
-   django.views.decorators.gzip
?                          ^
+   from django.views.decorators import gzip
?  +++++                        ^^^^^^^^
- 
- 0 objects imported automatically.
```
If you're interested to see why:
```py
>>> import django
>>> getattr(django, "db")  # fails
AttributeError ...
>>> import django.db  # coincidental import somewhere
>>> getattr(django, "db")  # succeeds
<module 'django.db' ...
```
----
`import_string()` is [https://docs.djangoproject.com/en/6.0/ref/utils/#django.utils.module_loading.import_string documented] to "return the attribute/class designated by the last name in the path". I guess a submodule is an "attribute" of a parent module, so it's suggested that this works, but looking at existing usage I found that often the assumption is that only classes and callables succeed. (I added tests that fail if this assumption is changed in b99c608ea10cabc97a6b251cdb6e81ef2a83bdcf.)


I'm suggesting we make `import_string()` fail more consistently when given a submodule, to surface these sneaky problems (after a deprecation).

----
Or, we could make `import_string()` handle either submodules or top-level modules as well.

Tim Graham [https://github.com/django/django/pull/18103#issuecomment-2135493131 observed that] werkzeug's implementation of `import_string()` handles both modules and submodules:
```py
        except ImportError:
            # support importing modules not yet set up by the parent module
            # (or package for that matter)
            module = import_string(module_name)
```
But that's not the history we have for this util. At the time, I thought it would be a bigger lift to audit all the call sites of `import_string()` and make sure they're OK with modules & submodules now succeeding. We also have several places coping with the ambiguity of modules and classes correctly:

```py
        # If import_module succeeds, entry points to the app module.
        try:
            app_module = import_module(entry)
...
        # If import_string succeeds, entry is an app config class.
        if app_config_class is None:
            try:
                app_config_class = import_string(entry)
...
        # If both import_module and import_string failed, it means that entry
        # doesn't have a valid value.
```
...but I'm alright with that assumption being questioned. I just think we're on the hook here for one behavior change or the other, since now it affects automatic shell imports.

PR incoming for the "reliably raise" option to aid the triage.

Reported in django ticket #36864: https://code.djangoproject.com/ticket/36864
