# Migration questioner complains about missing defaults for fields in unmanaged models

Since the improvement to tracking unmanaged model field alterations in #35813, the migration questioner (the interactive prompt) will now complain on missing defaults for altered fields.

In [https://github.com/django/django/pull/18651#issuecomment-5007220658 a post-merge comment] I suggested we could short-circuit in the questioner for unmanaged models, since if the model is ''unmanaged'' then it's not strictly true that it's "impossible" to add such fields, especially for unmanaged models that just shadow database views.

Sarah had a [https://github.com/django/django/pull/18651#pullrequestreview-4651959612 similar observation] before merge.

With this patch, I no longer needed to enter dummy values in the prompt:


_[a proposed patch was removed from this report]_
There would be a few other places to check to see where else we can short-circuit. What do folks think?

Reported in django ticket #37224: https://code.djangoproject.com/ticket/37224
