# Made makemigrations detect changes to unmanaged models

I believe there is a bug with the `makemigrations` command.

**The Issue/Bug:** Changes to unmanaged models are not being recognized by `makemigrations`. If those same changes are applied to a managed model, `makemigrations` recognizes the changes. 

The `makemigrations` command tracks the Creation of an unmanaged model, the Deletion of an unmanaged model, but does not track changes to the attributes/fields of an unmanaged model (see example below for more depth).

**Concerns/Discussion:** If you create an unmanaged model, make the initial migration and then have to change a field on it, `makemigrations` will not detect the change you made. At that point, your migrations (the 'historical reference') are out of sync with the current reality of the model. 

I have an if this is unclear.
For this example let's assume we have two models: `UnmanagedThing` and `ManagedThing` (unmanaged and managed, respectively)


```
class UnmanagedThing(models.Model):
    """
    This model represents an unmanaged Thing.
    """

    id = models.IntegerField(
        db_column="thingID", primary_key=True
    )
    thing_number = models.CharField(max_length=16, db_column="thingNumber")
    thing_name = models.CharField(max_length=50, db_column="thingName")
    grade_level = models.CharField(max_length=2, db_column="gradeLevel")

    class Meta:
        """Meta options for the UnmanagedThing model."""

        verbose_name = "Unmanaged Thing"
        verbose_name_plural = "Unmanaged Things"
        managed = False
        db_table = "some_table_name"

    def __str__(self) -> str:
        """Return the course name."""
        return f"{self.thing_name}"

class ManagedThing(models.Model):
    """
    This model represents an unmanaged Thing.
    """

    id = models.IntegerField(
        db_column="thingID", primary_key=True
    )
    thing_number = models.CharField(max_length=16, db_column="thingNumber")
    thing_name = models.CharField(max_length=50, db_column="thingName")
    grade_level = models.CharField(max_length=2, db_column="gradeLevel")

    class Meta:
        """Meta options for the UnmanagedThing model."""

        verbose_name = "Unmanaged Thing"
        verbose_name_plural = "Unmanaged Things"

    def __str__(self) -> str:
        """Return the course name."""
        return f"{self.thing_name}"

```
If I run `makemigrations` I get the expected `0001...` migration file and I see both models created with their respective fields/options.

If I change `thing_name` to be an `IntegerField` on the managed model and run `makemigrations`, I see a `0002...` migration file created with the expected 'AlterField' inside of it.

If I change `thing_name` to be an `IntegerField` on the unmanaged model and run `makemigrations`, I see "No changes detected" and nothing is created. However, now there is a disconnect between my model and what is recorded in migrations.

Everything else works similarly between the two; if I delete either one, it's recorded in a migration file. If I change the unmanaged model to 'managed', it creates a migration file for that (and subsequently begins tracking changes as expected with `makemigrations`)
 
Per the django docs: " You should think of migrations as a version control system for your database schema. `makemigrations` is responsible for packaging up your model changes into individual migration files - analogous to commits"; it's not behaving that way currently, so I believe this to be a valid bug worth fixing if the docs 

Per the django forums: "This lack of proper tracking might explain surface bugs like: [https://code.djangoproject.com/ticket/27319]"

Additional Suggestions: I think an option to exclude specific models or just exclude all unmanaged models would be something worth adding in the event we did not want to track historical changes to an unmanaged model or have it recorded in migrations.

Reported in django ticket #35813: https://code.djangoproject.com/ticket/35813
