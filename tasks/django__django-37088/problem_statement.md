# path based MediaAsset equality

This is a spin-off from here: https://github.com/django/django/pull/21239#issuecomment-4396168812

Currently `MediaAsset.__eq__` compares only the path.

This approach was deliberately chosen to benefit performance.

However, in the case of `link`-elements and even `script` this approach can break.
For a link, `rel=stylesheet` and `rel=prefetch` can share the same path. Prefetching is also not too crazy a use case; someone will probably try to do it.

A compromise could be to define an explicit list of attributes to compare, instead of doing a full dictionary comparison via `attributres`.
Something like:


_[a proposed patch was removed from this report]_

Reported in django ticket #37088: https://code.djangoproject.com/ticket/37088
