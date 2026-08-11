# AlterField doesn't propagate type changes through transitive attname-based to_field references

When a relation uses an attname-based `to_field` such as `primary_id`, Django accepts and resolves it correctly, but `AlterField` does not always propagate type changes through transitive dependencies.

Minimal example:
```
    class Primary(models.Model):
        code = models.CharField(max_length=5, unique=True)

    class Related(models.Model):
        primary = models.OneToOneField(
            Primary,
            to_field="code",
            on_delete=models.CASCADE,
        )

    class Dependent(models.Model):
        related = models.ForeignKey(
            Related,
            to_field="primary_id",
            on_delete=models.CASCADE,
        )
```
If `Primary.code.max_length` is changed from 5 to 11, Django correctly updates `Related.primary_id`, but `Dependent.related_id` remains at `varchar(5)` instead of widening to `varchar(11)`.
== Behavior
Using:
- `to_field="primary"` works correctly
- `to_field="primary_id"` does not
However, Django currently accepts `primary_id` as a valid `to_field` reference because relation resolution uses `Options.get_field()`, and `get_field()` maps both the field name and the relation attname to the same field object.
That means if `ForeignKey(..., to_field="primary_id")` is accepted and resolved as valid, schema alteration should handle it the same way as `to_field="primary"`.
== Cause
The schema dependency walk in `django/db/backends/base/schema.py` uses `_related_non_m2m_objects()` and `_is_relevant_relation()` to discover fields whose database type must be updated.
Before the fix, `_is_relevant_relation()` compared only the altered field's `name` against `field.to_fields`.
In the example above, the recursive step compares:
- altered field name: `primary`
- dependent field `to_fields`: `["primary_id"]`
So the dependency is missed even though both names refer to the same remote field.
As a result, the transitive dependent column is excluded from schema propagation.
== Expected behavior
Altering `Primary.code` from `max_length=5` to `max_length=11` should also widen:
- `Related.primary_id`
- `Dependent.related_id`
regardless of whether the dependent relation was declared with:
- `to_field="primary"`
- `to_field="primary_id"`
== Fix
Treat attname-based `to_field` values as equivalent to the actual remote field when determining whether a relation depends on the altered field.
In practice, this means resolving each `to_field` through `remote_model._meta.get_field(...)` and comparing field identity, instead of only comparing raw field names.
SQLite also needs the same recursive dependency logic in its schema editor override when rebuilding related tables after altering unique fields.

Reported in django ticket #37060: https://code.djangoproject.com/ticket/37060
