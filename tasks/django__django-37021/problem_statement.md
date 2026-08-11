# Add a helper function to return the permission string representation to be used with `user.has_perm()`

When checking user's permission using `user.has_perm()`, I need to pass a string in the format of `{Permission.content_type.app_label}.{Permission.codename}`

However, the `Permission` object itself does not provide an easy way to return this string.
The `__str__` method of the `Permission` class returns a string of `content_type | name`. 

I think it would be great if the `Permission` class can provide the string representation that will allow us to check the permission without having to manually construct it ourselves.

My desired outcome is to be able to do the following.



```
user_permissions = Permission.objects.filter(...) 
for perm in user_permissions:
    if user.has_perm(perm.perm_string()):
        # let them do stuff
```
Currently I am doing it as follows:

```
if user.has_perm(f"{perm.content_type.app_label}.{perm.codename}"):
        # let them do stuff
```
Proposal:

To add a function within `Permission` class:

```
def perm_string(self): # feel free to suggest other name
    return f"{self.content_type.app_label}.{self.codename}"

```
If you agree, I would like to try to create the PR for this.

Reported in django ticket #37021: https://code.djangoproject.com/ticket/37021
