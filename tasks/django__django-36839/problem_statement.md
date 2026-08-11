# Renaming of content types on RenameModel operations silently passes when duplicates are found

When renaming a model, the `migrate` command will inject operations to rename content types. When a target content type already exists, the operation just silently skips the update:
```py
            content_type.model = new_model
            try:
                with transaction.atomic(using=db):
                    content_type.save(using=db, update_fields={"model"})
            except IntegrityError:
                # Gracefully fallback if a stale content type causes a
                # conflict as remove_stale_contenttypes will take care of
                # asking the user what should be done next.
                content_type.model = old_model
```
The rationale for skipping was discussed [https://github.com/django/django/pull/6612#issuecomment-219584224 here]:

> In this case I think the safe approach is simply to silently handle the integrity error and let the update_contenttypes's post_migrate handler prompt the user about what to do next.

But that `post_migrate` handler was later removed in 6a2af01452966d10155b720f4f5e7b09c7e3e419 in favor of a management command that can be run on demand, meaning the pass is now silent again, AFAICT.

I don't think the silent pass is desired. I can add more details if this isn't enough context, but I think it's worth an initial investigation.

Reported in django ticket #36839: https://code.djangoproject.com/ticket/36839
