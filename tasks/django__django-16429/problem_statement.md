# Allow refresh of path choices for FilePathField

As noted by a couple of people on django-users, FilePathField does not automatically refresh choices if files are add to or removed from the path being pointed to (http://groups.google.com/group/django-users/browse_thread/thread/6778fa138b848996 and http://groups.google.com/group/django-users/browse_thread/thread/403d872cf9433905).

A nice addition to FilePathField would be the ability to refresh the path choices on a per-request basis.

Reported in django ticket #16429: https://code.djangoproject.com/ticket/16429
