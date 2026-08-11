# Crash in Query.orderby_issubset_groupby for descending and random order_by strings

#26434 caused a crash. It can be reproduced with:

```
User.objects.values("is_staff").annotate(latest=Max("date_joined")).order_by("-latest").count()
```
You should see the following exception:

```
django.core.exceptions.FieldError: Cannot resolve keyword '-latest' into field. Choices are: activity_logs, date_joined, email, first_name, groups, id, is_active, is_administrator, is_staff, is_superuser, last_login, last_name, latest, logentry, module_access, password, user_permissions, username
```

Reported in django ticket #37047: https://code.djangoproject.com/ticket/37047
