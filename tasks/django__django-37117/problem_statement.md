# Admin: Change form actions should use ModelAdmin.get_queryset(request)

The change form action path in `_changeform_view` builds the queryset passed to action functions using `self.model._default_manager.get_queryset()` (options.py, introduced in f30acb1, #12090) instead of `self.get_queryset(request)`. The two diverge whenever a `ModelAdmin` overrides `get_queryset()` to use a non-default manager. Some common real-world case being a soft-delete (example below) or tenant-scoped pattern where the default manager filters out certain rows and `get_queryset()` opts into a broader set.

When a change form action is invoked on an object that is visible via `get_queryset(request)` but excluded by `_default_manager`, the action receives an empty queryset and silently does nothing. This could also have consequences on annotated queries.

To reproduce, given a model and model admin as below, try to "restore" a deleted `Document` instance. Using the `main` code, the action results in a "0 document(s) restored" since the action receives an empty queryset (ActiveDocumentManager excludes deleted=True) and calls queryset.update(deleted=False) on zero rows. The document remains deleted.

```python
# models.py

from django.db import models


class ActiveDocumentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted=False)


class Document(models.Model):
    title = models.CharField(max_length=200)
    deleted = models.BooleanField(default=False)

    objects = ActiveDocumentManager()  # default: active documents only
    all_objects = models.Manager()     # unfiltered

    def __str__(self):
        return self.title

# admin.py

from django.contrib import admin
from django.contrib.admin.options import ActionLocation

from .models import Document


@admin.action(description="Restore document", location=ActionLocation.CHANGE_FORM)
def restore_document(modeladmin, request, queryset):
    queryset.update(deleted=False)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    actions = [restore_document]
    list_display = ["title", "deleted"]

    def get_queryset(self, request):
        # Use all_objects so admins can view and act on soft-deleted documents.
        return Document.all_objects.all()
```
Working on a patch including a regression test.

Reported in django ticket #37117: https://code.djangoproject.com/ticket/37117
