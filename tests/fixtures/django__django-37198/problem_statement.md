# `content_disposition_header()` mis-quotes filenames ending in a newline

`django.utils.http.content_disposition_header()` is supposed to decide between
two encodings for a filename: the plain `filename="..."` form when every
character is safely representable in a quoted string, and the percent-encoded
`filename*=utf-8''...` form otherwise.

A filename whose last character is a newline is taking the wrong branch. The
newline is emitted raw inside the quoted form instead of being percent-encoded.

## Reproduction

```python
>>> from django.utils.http import content_disposition_header
>>> content_disposition_header(True, "example\n")
'attachment; filename="example\n"'
```

Expected:

```
"attachment; filename*=utf-8''example%0A"
```

A bare `"\n"` as the whole filename is affected the same way.

Note that a newline in the *middle* of a filename is already handled correctly:

```python
>>> content_disposition_header(True, "some\nfile")
"attachment; filename*=utf-8''some%0Afile"
```

so the problem is specific to the trailing position.

## Why it matters

`Content-Disposition` is a response header. Emitting an unencoded newline in a
header value is a header-injection risk, and RFC 9110 does not permit a bare
newline inside a quoted-string.
