# Unhandled LookupError in multipart parser when RFC 2231 encoding name is invalid

When a multipart form upload includes an RFC 2231 encoded `filename*` parameter with an invalid encoding name (e.g., `filename*=BOGUS''test%20file.txt`), [[https://github.com/django/django/blob/main/django/utils/http.py#L332|parse_header_parameters()]], [[https://github.com/django/django/blob/main/django/utils/http.py|django/utils/http.py]] passes the encoding to `urllib.parse.unquote()`, which raises `LookupError`.

The caller in [[https://github.com/django/django/blob/main/django/http/multipartparser.py#L729|django/http/multipartparser.py]] only catches `ValueError`:

```python
except ValueError:  # Invalid header.
    continue
```
Since `LookupError` is not a subclass of `ValueError`, the exception propagates and results in a 500 Internal Server Error.


== Steps to Reproduce ==
1. Create a simple upload view:
```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
def upload(request):
    if request.method == "POST" and request.FILES:
        return JsonResponse({"filename": request.FILES["file"].name})
    return JsonResponse({"error": "No file"}, status=400)
```
2. Send a multipart request with a bogus encoding:
```python
import http.client
boundary = "----PoC"
body = (
    f"--{boundary}\r\n"
    f"Content-Disposition: form-data; name=\"file\"; "
    f"filename*=BOGUS''test%20file.txt\r\n"
    f"Content-Type: application/octet-stream\r\n"
    f"\r\n"
    f"content\r\n"
    f"--{boundary}--\r\n"
)
conn = http.client.HTTPConnection("localhost", 8000)
conn.request("POST", "/upload/", body=body.encode(),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
print(conn.getresponse().status)  # Returns 500
```
The filename must contain at least one percent-encoded character (e.g., `%20`) for `unquote()` to invoke the codec.

Confirmed on Django 6.0.2, Python 3.14.

PR link: https://github.com/django/django/pull/20714

Reported in django ticket #36931: https://code.djangoproject.com/ticket/36931
