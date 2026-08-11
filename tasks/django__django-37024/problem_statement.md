# Integer SITE_ID check incorrect when a different primary key type is used

To catch a programmer mistake where the `SITE_ID` setting is defined with an incorrect type (e.g. `SITE_ID = "1"`), #31802 added a system check that only allows `SITE_ID` to be an `int` or `None`. This forces third-party databases with non-integer primary keys like MongoDB (which uses `ObjectId`) to silence this check.

It would be more appropriate if this check performed the validation based on `Site._meta.pk` rather than with hardcoded types.

I thought of a few options:

1. Use `Site._meta.pk.to_python(settings.SITE_ID)` to validate the `SITE_ID`, relying on it to raise `ValidationError` for unexpected types. This won't work because `AutoField.to_python()` accepts strings that coerce to integer which are values the original fix was intended to reject.

2. Use `Site._meta.pk.to_python(settings.SITE_ID)` but also check if `settings.SITE_ID != Site._meta.pk.to_python(settings.SITE_ID)`. This would catch invalid values that `to_python()` coerces to the correct type.

3. Add `Field.expected_type` which could be `int`, `ObjectId`, or whatever. The implementation of the check could continue to use `isinstance()`. The downside is that adding a new attribute to the `Field` API would be non-trivial.

I've implemented option #2.

Reported in django ticket #37024: https://code.djangoproject.com/ticket/37024
