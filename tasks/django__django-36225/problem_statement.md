# createsuperuser validation breaks if USERNAME_FIELD is distinct but user manager deliberately lacks get_by_natural_key()

We have a custom user model defined, that does not have a natural key and in fact all fields (except pk) may be duplicated. That is because we can have "special" users that do not have an email.

Our model looks like this (minimal user model without a natural key implementation):

```python
from django.contrib.auth.models import PermissionsMixin
from django.db import models

class UserProfile(PermissionsMixin, models.Model):
    # null=True because certain external users don't have an address
    email = models.EmailField(max_length=255, unique=True, blank=True, null=True, verbose_name="email address")
    password = models.CharField("password", max_length=128)

    @property
    def is_anonymous(self):
        return False

    @property
    def is_authenticated(self):
        return True

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["password"]
```
Now, using `./manage.py createsuperuser` is no longer possible. After entering an email address:
```python
Email address: user@example.com
Traceback (most recent call last):
  File "./manage.py", line 22, in <module>
    main()
  File "./manage.py", line 18, in main
    execute_from_command_line(sys.argv)
  File ".../lib/python3.10/site-packages/django/core/management/__init__.py", line 442, in execute_from_command_line
    utility.execute()
  File ".../lib/python3.10/site-packages/django/core/management/__init__.py", line 436, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File ".../lib/python3.10/site-packages/django/core/management/base.py", line 413, in run_from_argv
    self.execute(*args, **cmd_options)
  File ".../lib/python3.10/site-packages/django/contrib/auth/management/commands/createsuperuser.py", line 90, in execute
    return super().execute(*args, **options)
  File ".../lib/python3.10/site-packages/django/core/management/base.py", line 459, in execute
    output = self.handle(*args, **options)
  File ".../lib/python3.10/site-packages/django/contrib/auth/management/commands/createsuperuser.py", line 132, in handle
    error_msg = self._validate_username(
  File ".../lib/python3.10/site-packages/django/contrib/auth/management/commands/createsuperuser.py", line 305, in _validate_username
    self.UserModel._default_manager.db_manager(database).get_by_natural_key(
AttributeError: 'Manager' object has no attribute 'get_by_natural_key'
```
`Command._validate_username` does check if the username field is unique by looking at the `unique` flag passed to the field. However, we also set `null=True`, so our username is not unique in the sense that a `get_by_natural_key` can be implemented at all.

The create superuser command should either check for a nullable or blank username field in addition to the `unique` flag, or directly check if the user model has the attribute `get_by_natural_key` defined.

Reported in django ticket #36225: https://code.djangoproject.com/ticket/36225
