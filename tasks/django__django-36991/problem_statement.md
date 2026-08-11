# LookupError crash (HTTP 500) in parse_header_parameters() when Content-Type header contains RFC 2231 parameter with invalid encoding name

parse_header_parameters() in django/utils/http.py crashes with an unhandled LookupError when it receives a Content-Type header containing an RFC 2231 encoded parameter (e.g. charset*=) where the encoding portion is an invalid codec name. This causes Django's WSGI request initialization to raise an uncaught exception, resulting in HTTP 500 instead of HTTP 400.

**Security note:** This crash can be triggered by any unauthenticated request. The crash occurs inside WSGIRequest.__init__() during WSGI request construction — before Django processes the Authorization header, before authentication middleware runs, and before any view-level access control is evaluated. No valid credentials are required to trigger the 500 response.

**Minimal reproduction:**

Request:

```
GET /api/v1/ HTTP/2
Host: host.com
Content-Type: ;*=''%
```
```
from django.utils.http import parse_header_parameters
parse_header_parameters("text/plain; charset*=BOGUS''value")
# → LookupError: unknown encoding: BOGUS
```
**Full traceback (from production, Python 3.13, Django 5.1.x):**

```
File "django/core/handlers/wsgi.py", line 73, in __init__
self._set_content_type_params(environ)
File "django/http/request.py", line 102, in _set_content_type_params
self.content_type, self.content_params = parse_header_parameters(
meta.get("CONTENT_TYPE", "")
)
File "django/utils/http.py", line 356, in parse_header_parameters
value = unquote(value, encoding=encoding)
File "urllib/parse.py", line 712, in unquote
return ''.join(_generate_unquoted_parts(string, encoding, errors))
File "urllib/parse.py", line 688, in _generate_unquoted_parts
yield _unquote_impl(ascii_match[1]).decode(encoding, errors)
LookupError: unknown encoding: <garbage value from Content-Type header>
```
**Root cause:**

In parse_header_parameters(), when a parameter name ends with * and the value contains exactly 2 single quotes, Django treats it as an RFC 2231 encoded parameter and extracts the encoding name from the value before passing it to urllib.parse.unquote():

```
if has_encoding:
encoding, lang, value = value.split("'")
value = unquote(value, encoding=encoding) # no validation of 'encoding'
```
If encoding is not a valid Python codec name, bytes.decode(encoding) inside urllib.parse.unquote() raises LookupError. This is not caught anywhere in the call stack. Since the crash happens inside WSGIRequest.__init__(), no Django middleware or DRF parser can intercept it.

**Expected behavior:**

Invalid encoding names in RFC 2231 Content-Type parameters should result in an HTTP 400 Bad Request, not an HTTP 500 Internal Server Error.

**Proposed fix:**

Wrap the unquote() call in a try/except (LookupError, UnicodeDecodeError) and raise ValueError (which callers already handle) or django.core.exceptions.BadRequest:


```
if has_encoding:
encoding, lang, value = value.split("'")
try:
value = unquote(value, encoding=encoding)
except (LookupError, UnicodeDecodeError):
raise ValueError(f"Invalid encoding '{encoding}' in Content-Type parameter.")
```
**Notes:**

- This code area was reviewed following ticket #35440 (security report, concluded non-security). The rewrite using email.Message was attempted and reverted in #36520 due to performance regression. Neither addressed this specific LookupError path.
- urllib.parse.unquote() is behaving correctly — the bug is that Django passes an unvalidated, user-controlled encoding name to it.
- Discoverable via API fuzzing tools (e.g. Mayhem4API).

Reported in django ticket #36991: https://code.djangoproject.com/ticket/36991
