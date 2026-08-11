# Renaming a model doesn't rename the permission name and codename

After a `RenameModel` operation, new permissions are created with the name and codename of the new model name rather than renaming the permissions with the old model name. It should be feasible to fix by using an approach similar to f179113e6cbc8ba0a8d4e87e1d4410fb61d63e75 where a `RenamePermission` operation is injected in the plan after each `RenameModel` operation.

#26756 requires the same approach except that the `RenamePermission` operation must be inserted after `AlterModelOptions` operations with a `verbose_name` key.

Reported in django ticket #27489: https://code.djangoproject.com/ticket/27489
