# aiterator() missing check for chunk_size=None after prefetch_related()

`aiterator()` is missing the [https://github.com/django/django/blob/4bbc27c8686f10f9556cef02dbfa9f5157fbcf56/django/db/models/query.py#L566 check] found in `iterator()` for `chunk_size=None` after `prefetch_related()`:

`iterator()` version:
```py
        if chunk_size is None:
            if self._prefetch_related_lookups:
                raise ValueError(
                    "chunk_size must be provided when using QuerySet.iterator() after "
                    "prefetch_related()."
                )
```
I think this should have been implemented in #34331.

The rationale for the check was to alert users that the number of queries could spike with small batch sizes, which you might be tempted to minimize if prioritizing memory optimizations.

Reported in django ticket #37143: https://code.djangoproject.com/ticket/37143
