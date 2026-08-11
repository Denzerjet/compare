# alogout() doesn't clear request.user

As of Django 6.0, `alogout()` no longer clears `request.user`, only `request.auser`. If code accesses `request.user` before `RemoteUserMiddleware` (or similar) runs `alogout()`, then it is possible for `request.user` to be stale, and for a resource behind authentication to be visible to a logged-out user.

`user` and `auser` aren't really two concepts: just two getters for the same underlying concept. (Thanks, function color problem!)


(I'm suggesting this was an oversight in 31a43c571f4d036827d4fd7a5f615591637dc1be. This was [https://github.com/django/django/pull/19709#issuecomment-3162977011 discussed] during development, but it may not have been clear how this would arise in practice.)

The security team considered a report about this suggesting the following order of middlewares:

```py
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "app.middleware.MaterializeUserMiddleware",  # e.g. a logging middleware like Sentry
    "django.contrib.auth.middleware.RemoteUserMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
]
```
The problem does not reproduce if `RemoteUserMiddleware` is moved one position earlier. The security team closed the report on this basis (that is, anything responsible for logout should happen before other code that might be interested in that logout). Our [https://docs.djangoproject.com/en/6.0/howto/auth-remote-user/#configuration docs say] `RemoteUserMiddleware` should be placed "after" `AuthenticationMiddleware`, but does not clarify whether this entails ''directly'' after.

Still seems like something to fix to make auth easier to reason about.

Thanks Peng Zhou for the report.

Reported in django ticket #37017: https://code.djangoproject.com/ticket/37017
