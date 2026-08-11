# HttpRequest.body raises ValueError for malformed CONTENT_LENGTH

Accessing request.body raises an unhandled `ValueError` when `META["CONTENT_LENGTH"]` isn't a valid integer:

```
ValueError: invalid literal for int() with base 10: '10,20'
```
This can happen with `ASGIRequest` if duplicate `Content-Length` headers are comma-joined into a single META value. Even when such requests are usually rejected by common HTTP parsers, `HttpRequest.body` is currently inconsistent with other Django code paths.


```
WSGIRequest.__init__(), MultiPartParser.__init__(), and
django.core.servers.basehttp all wrap int(CONTENT_LENGTH) in:

    try:
        ...
    except (ValueError, TypeError):
        content_length = 0

```
`HttpRequest.body` is the only place that calls `int(CONTENT_LENGTH)` without
that guard.

Minimal reproduction:

```
    from io import BytesIO
    from django.core.handlers.asgi import ASGIRequest
    from django.test import AsyncRequestFactory

    scope = AsyncRequestFactory()._base_scope(method="POST", path="/")
    scope["headers"] = [
        (b"content-type", b"text/plain"),
        (b"content-length", b"10,20"),
    ]

    ASGIRequest(scope, BytesIO(b"hello world body")).body
```
Expected behavior:
`request.body` should handle malformed `CONTENT_LENGTH` consistently with `WSGIRequest` and `MultiPartParser`, falling back to 0 instead of surfacing a raw `ValueError`.

Actual behavior:
`request.body` raises `ValueError`.

I have a patch and regression test.

Reported in django ticket #37103: https://code.djangoproject.com/ticket/37103
