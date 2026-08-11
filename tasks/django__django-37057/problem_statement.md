# UniqueConstraint incorrectly raises ValidationError on nullable fields in condition

== Summary
When a `UniqueConstraint` has a `condition` that references a nullable field (e.g., `condition=Q(cash_register_type=10)` on a nullable `PositiveSmallIntegerField`), Django's `UniqueConstraint.validate()` incorrectly reports a constraint violation if the instance being saved has `cash_register_type=None` and another record matching the condition already exists.

''Tested in Django==5.2.4 (with Postgres 17) and 6.0.4 (with Postgres 18)''


== Steps to Reproduce

```
from django.db import models

class Location(models.Model):
    name = models.CharField(max_length=100)

class Device(models.Model):
    class CashRegisterType(models.IntegerChoices):
        MASTER = 10, "Master"
        SLAVE  = 20, "Slave"
    name = models.CharField(max_length=100)
    pos_location = models.ForeignKey(Location, on_delete=models.CASCADE)
    cash_register_type = models.PositiveSmallIntegerField(
        choices=CashRegisterType,
        blank=True, null=True, default=None,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pos_location"],
                condition=models.Q(cash_register_type=10),
                name="unique_master_cash_register",
                violation_error_message="Only one Master per POSLocation.",
            )
        ]
```
Create one Device with `cash_register_type` Master and creating another one for the same Location with `cash_register_type=None` will raise ValidationError
```
from myapp.models import Location, Device

loc = Location.objects.create(name="Store 1")

# 1. Create a Master -- works
master = Device.objects.create(
    name="CashRegister A", pos_location=loc, cash_register_type=10
)

# 2. Create a second Device with cash_register_type=None
# while a Master already exists -- BUG
register_b = Device(
    name="Device B", pos_location=loc, cash_register_type=None
)
register_b.full_clean()    # raises ValidationError
```
== Workaround
Add an explicit `isnull=False` check to the condition:
`condition=models.Q(cash_register_type=10) & models.Q(cash_register_type__isnull=False)`
Although `10` should already be `isnull=False`.

Reported in django ticket #37057: https://code.djangoproject.com/ticket/37057
