# request.META["HTTP_" + self.header] in RemoteUserMiddleware __acall__ does not sound correct

I've been investigating why https://github.com/adelton/django-identity-external no longer works with Django 5.2. The https://docs.djangoproject.com/en/5.2/releases/5.2/#django-contrib-auth talks about new async auth functions. I have no idea if the async functions are part of the problem I try to solve but it made me look at the code changes.

The PR https://github.com/django/django/pull/18036 for https://code.djangoproject.com/ticket/35303 added `__acall__` with code
```
+        try:
+            username = request.META["HTTP_" + self.header]
+        except KeyError:
+            # If specified header doesn't exist then remove any existing
+            # authenticated remote-user, or return (leaving request.user set to
+            # AnonymousUser by the AuthenticationMiddleware).
```
among others.

However, the code in `__call__` (previously `process_request`) has code
```
        try:
            username = request.META[self.header]
        except KeyError:
            # If specified header doesn't exist then remove any existing
            # authenticated remote-user, or return (leaving request.user set to
            # AnonymousUser by the AuthenticationMiddleware).
            if self.force_logout_if_no_header and request.user.is_authenticated:
```
Since they implement the same logic, the discrepancy is worrying. I believe the `"HTTP_"` prefix is wrong -- if the user (admin) wants to consume some HTTP header, let them configure the value with the `HTTP_` prefix already.

This also shows that there don't seem tests covering the `RemoteUserMiddleware`, or the problem would have been caught.

Reported in django ticket #36300: https://code.djangoproject.com/ticket/36300
