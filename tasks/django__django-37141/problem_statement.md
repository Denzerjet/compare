# sendtestemail needs a way to specify the MAILERS configuration

The [https://docs.djangoproject.com/en/stable/ref/django-admin/#sendtestemail sendtestemail] management command always uses the default `MAILERS` configuration. There's currently no way to test other configurations with it.

We should add an optional `--using ALIAS` argument to `sendtestemail` to specify the `MAILERS` configuration:

```shell
./manage.py sendtestemail --using notifications to@example.com
./manage.py sendtestemail --managers --using internal
```
If `--using` is not provided, `sendtestemail` would use the default `MAILERS` configuration.

[This was recommended as early follow-on work [https://github.com/django/deps/blob/main/accepted/0018-mailers.md#future-sendtestemail-using-option in DEP 0018]. I'm opening it as "Cleanup" because it feels like a missing piece of #35514 rather than a new feature. Or we may want to treat it as a "Bug" so it gets backported to 6.1 (if it makes it in before beta).]

Reported in django ticket #37141: https://code.djangoproject.com/ticket/37141
