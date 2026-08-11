# Client.force_login won't work for permission-only backends inheriting from BaseBackend

This is a follow up to #27542.

Take the `MagicAdminBackend` from the [https://docs.djangoproject.com/en/6.0/topics/auth/customizing/#handling-authorization-in-custom-backends documentation]. It is an Authentication Backend that inherits from `BaseBackend` and overrides the `has_perm` method. This leaves it with the default `get_user` method returning `None`, making it eligible for `Client.force_login`.

Some libraries like `django-rules` and `django-guardian` work around this by not inheriting from `BaseBackend`, and not adding a `get_user` method, but:
* this goes against the documentation, which states that both `get_user` and `authenticate` are required, and permission related methods are optional
* now they don't automatically gain the `async` functionality, making it harder for users to integrate those libraries in an `async` context

I don't know a good way around this. Some ideas are:

**Add some introspection capabilities to BaseBackend**
I was think something like:
```
class BaseBackend:
    supports_authentication = True
    supports_permissions = True

class ObjectPermissionBackend(BaseBackend):
    supports_authentication = False
    supports_permissions = True
```
This way we could change `(a)authenticate` and `force_login` to skip backends that do not support autentication, and `(a)has_perm` to skip backends that do not support permissions.

```
def _get_compatible_backends(request, **credentials):
    for backend, backend_path in _get_backends(return_tuples=True):
        if not getattr(backend, "supports_authentication", True):
            continue

        ... Check signature and so on

def _user_has_perm(user, perm, obj):
    for backend in auth.get_backends():
        if not getattr(backend, "supports_permissions", True):
            continue

        if not hasattr(backend, "has_perm"):
            continue
        
        ... Check permission
```
**Call `get_user` inside `force_login`**
Use the first backend that returns something. This was suggested on #27542, but it could be really slow and might introduce some side effects

**Updating the documentation**
Simply update the documentation stating that:
* `get_user` required only if the backend can authenticate users (`authenticate` returns something)
* `Client.force_login` selects the first backend that has a `get_user`.

Reported in django ticket #36837: https://code.djangoproject.com/ticket/36837
