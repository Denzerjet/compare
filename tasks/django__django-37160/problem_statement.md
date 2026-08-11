# Make admin views consistently raise PermissionDenied (403) when lacking model permissions

The Security Team occasionally gets reports about PK enumeration in admin views. We close them, since:
- admin users are trusted
- if PK obscurity is important, then you should choose unguessable PKs

Usually the reports ask us to consider models for which a staff user lacks view permission.

We would evaluate a public cleanup that makes the various admin views consistent in how they treat nonexistent PKs for staff users lacking view permissions.

Two cases were recently called to our attention:

- The "view_on_site" route (wrapping the contenttypes shortcut) redirects without checking permissions, giving either a 302 or 404, instead of a 403.
- The "history_view" route calls `self.get_object()` and returns the "does not exist" redirect *before* checking `has_view_or_change_permission()`, giving a 302 for a missing PK and 403 for an existing one.

These are both in contrast to the autocomplete_view and changeform view, which are more careful to return 403 when users lack view permissions.

Reported in django ticket #37160: https://code.djangoproject.com/ticket/37160
