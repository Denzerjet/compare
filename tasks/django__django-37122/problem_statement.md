# JSONField has_changed doesn't reflect disabled correctly

Problem:

A disabled JSONField still reports changes via has_changed.

Why?


```
def has_changed(self, initial, data):
    # here we miss the check for disabled
    if super().has_changed(initial, data):
        return True
    ...

```
As we see, has_changed from the base is called and if successful, True is returned. But we have no additional check for disabled.

Reported in django ticket #37122: https://code.djangoproject.com/ticket/37122
