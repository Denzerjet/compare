# content_disposition_header emits invalid header for a filename with a trailing newline

`content_disposition_header()` is meant to emit the percent-encoded `filename*=utf-8''` form for any filename that is not a valid RFC 9110 quoted-string, and to only use the bare quoted form for filenames that are. Its check has a blind spot for a trailing newline:

```
    >>> from django.utils.http import content_disposition_header
    >>> content_disposition_header(True, "report.pdf\n")
    'attachment; filename="report.pdf\n"'
    >>> content_disposition_header(True, "\n")
    'attachment; filename="\n"'

```
The returned value contains a raw newline, so setting it as a header raises `BadHeaderError (Django responses)`, and `boto3/http.client` raises `ValueError("Invalid header value ...")` — an uncaught 500 for anyone serving a user-supplied filename that ends in a newline. (A newline *elsewhere* in the filename is handled correctly.)

Reported in django ticket #37198: https://code.djangoproject.com/ticket/37198
