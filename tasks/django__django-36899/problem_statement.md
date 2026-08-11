# Implement `Session.__bool__`

It's often useful to check whether the user has a session, for example to avoid creating one unnecessarily. Since `request.session` is always populated when `SessionMiddleware` is used, it's better to check whether the session is empty.

#36898 documents `Session.is_empty()` which achieves this, but it could also be nice if `Session` supported a boolean check directly through `__bool__`, which would just call `is_empty` internally.

This would mean `if request.session` works as expected. The downside being `if getattr(request, "session", None)` would be `False` when sessions are being used, but the session is empty (arguably `hasattr` would be better there anyway).

Reported in django ticket #36899: https://code.djangoproject.com/ticket/36899
