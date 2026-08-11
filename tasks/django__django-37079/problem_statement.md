# RemoteUserMiddleware assumes all ASGI requests will be handled by its async path

As pointed out in a [https://github.com/django/django/pull/21079#discussion_r3070329801 review], `RemoteUserMiddleware` doesn't account for the case where an ASGI request passes through (sync) `process_request()` due to subsequent sync-only middleware in the stack. This could cause the wrong header to be looked up.

Bug in 50f89ae850f6b4e35819fe725a08c7e579bfd099.

Reported in django ticket #37079: https://code.djangoproject.com/ticket/37079
