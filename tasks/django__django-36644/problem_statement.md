# Enable using an empty order_by() to disable implicit primary key ordering in first()

As discussed in https://github.com/django/new-features/issues/71, update the interaction between `order_by` and `first` to enable this behaviour:

```
# Existing
MyModel.objects.first()  # first, ordered by `pk`
MyModel.objects.order_by("pk").first()  # as above
MyModel.objects.order_by("name").first()  # first, ordered by `name`

# New
MyModel.objects.order_by().first()  # first, but in whatever order the database returns it
```
This will interact with [https://docs.djangoproject.com/en/5.2/ref/models/options/#django.db.models.Options.ordering default orderings (`Meta.ordering`)], which will need some careful handling.

Reported in django ticket #36644: https://code.djangoproject.com/ticket/36644
