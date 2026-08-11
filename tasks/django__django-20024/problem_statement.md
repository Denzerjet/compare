# QuerySet.exclude() does not work with lists containing a 'None' element.

For example:
```
Entry.objects.exclude(foo__in=[None, 1])
```
It is supposed to return all items whose foo field is not None or 1, but it actually returns an empty query set.

Reported in django ticket #20024: https://code.djangoproject.com/ticket/20024
