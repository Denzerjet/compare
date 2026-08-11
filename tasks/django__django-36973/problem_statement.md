# fields.E348 check should check against the accessor_name instead of the model name

when running manage.py I hit erroneous fields.E348 check. The system check is supposed to examine if ManyToOne/ManyToMany field <related_name> for <model>.<field name> clashes with the name of a model manager. However, instead of checking the related_name (i.e. <fieldname>_set or manually set related_name=<related_name>) it gets the actual field name of the foreign key.

As shown in the original check function below

```
    def _check_conflict_with_managers(self):
        errors = []
        manager_names = {manager.name for manager in self.opts.managers}
        for rel_objs in self.model._meta.related_objects:
            related_object_name = rel_objs.name
            if related_object_name in manager_names:
                field_name = f"{self.model._meta.object_name}.{self.name}"
                errors.append(
                    checks.Error(
                        f"Related name '{related_object_name}' for '{field_name}' "
                        "clashes with the name of a model manager.",
                        hint=(
                            "Rename the model manager or change the related_name "
                            f"argument in the definition for field '{field_name}'."
                        ),
                        obj=self,
                        id="fields.E348",
                    )
                )
        return errors
```
it compares a model's managers' name and its related object field name. 

` related_object_name = rel_objs.name `

<!-- hand-edited: do not regenerate -->

Reported in django ticket #36973: https://code.djangoproject.com/ticket/36973
