# Saving related objects with generated primary keys doesn't update assigned relations

With these models:
```py
class DBDefaultsFunctionPK(models.Model):
    uuid = models.UUIDField(primary_key=True, db_default=UUID4())

    class Meta:
        required_db_features = {
            "supports_uuid4_function",
            "supports_expression_defaults",
        }


class DBDefaultsFunctionPKChild(DBDefaultsFunctionPK):
    parent = models.OneToOneField(
        DBDefaultsFunctionPK,
        models.CASCADE,
        primary_key=True,
        db_default=UUID4(),
        related_name="child",
    )

    class Meta:
        required_db_features = {
            "supports_uuid4_function",
            "supports_expression_defaults",
        }
```
This test fails:
```py
    @skipUnlessDBFeature(
        "can_return_rows_from_bulk_insert",
        "supports_expression_defaults",
        "supports_uuid4_function",
    )
    def test_foreign_key_db_default_expression_via_parent(self):
        parent = DBDefaultsFunctionPK()
        obj = DBDefaultsFunctionPKChild(parent=parent)
        parent.save()
        obj.save()
        self.assertEqual(obj.pk, parent.pk)
```
```
======================================================================
FAIL: test_foreign_key_db_default_expression_via_parent (field_defaults.tests.DefaultTests.test_foreign_key_db_default_expression_via_parent)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/jwalls/django/tests/field_defaults/tests.py", line 152, in test_foreign_key_db_default_expression_via_parent
    self.assertEqual(obj.pk, parent.pk)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
AssertionError: UUID('fdfe6046-e662-4c36-a2e1-b10677d0ccb3') != UUID('ddeef3dd-52bc-4b35-b643-4634876a4acc')

----------------------------------------------------------------------
Ran 1 test in 0.016s

FAILED (failures=1, errors=1)
```
----
A similar version of the test using `Now()` instead of `UUID4()` fails on 5.2 (since `UUID4()` is not available there), but I ran into issues with trying to use datetimes in FK constraints on sqlite, so I'm happy to take advice on the best examples to build these models with, as I could be glazing over something obviously better.
----
This is the "separate non-release-blocker ticket" mentioned in #37238, and the underlying reason for the relaxed assertions on the PR for it.

Reported in django ticket #37239: https://code.djangoproject.com/ticket/37239
