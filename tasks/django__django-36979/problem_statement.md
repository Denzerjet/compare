# GenericInlineModelAdmin doesn't respect ModelAdmin.get_exclude()

The `ModelAdmin.get_exclude()` hook was added in #24941, however, `GenericInlineModelAdmin` [https://github.com/django/django/blob/787166fe27b0e7c7f97505da5766cfa72e76ae25/django/contrib/contenttypes/admin.py#L103 doesn't use it].

Reported in django ticket #36979: https://code.djangoproject.com/ticket/36979
