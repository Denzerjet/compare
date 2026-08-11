# bulk_create fails when related objects got PKs later

This is a regression betwen Django 5.2 and 6.0.

Here's a short reproducer test that, when added to `tests/bulk_create/tests.py` fails with an AssertionError within `bulk_create`.

```
    @skipUnlessDBFeature("can_return_rows_from_bulk_insert")
    def test_pk_from_related_instance_saved_after_init(self):
        country = Country(name="Syldavia", iso_two_letter="SW")
        related = RelatedModel(country=country)
        country.save()
        RelatedModel.objects.bulk_create([related])
        self.assertEqual(related.country_id, country.pk)
```
Failure:

```
  File "/Users/krab/workspace/django/tests/bulk_create/tests.py", line 901, in test_pk_from_related_instance_saved_after_init
    RelatedModel.objects.bulk_create([related])
    ^^^^^^^^^^^^^^^
  File "/Users/krab/workspace/django/django/db/models/manager.py", line 87, in manager_method
    return getattr(self.get_queryset(), name)(*args, **kwargs)
    ^^^^^^^
  File "/Users/krab/workspace/django/django/db/models/query.py", line 913, in bulk_create
    assert len(returned_columns) == len(objs_without_pk)
    ^^^
```
It looks like Django used to support this case intentionally, calling `._prepare_related_fields_for_save(operation_name="bulk_create")` within `bulk_create` but a recent change breaks that.

I've never contributed to Django, but I'm willing to work on a fix if you're interested.

Reported in django ticket #37234: https://code.djangoproject.com/ticket/37234
