# Prevent header injection through malformed response reason phrase

`HttpResponse.reason_phrase` is not correctly sanitized when creating a response body:
 
```python
HttpResponse(
    "body",
    reason="OK\r\nX-Injected-header: yes",
)
```
This results in an extra header in the response, which is not present in `.headers`.

The [https://peps.python.org/pep-0333/#the-start-response-callable WSGI spec] requires that the status line (which contains the reason phrase) must not contain whitespace or other control characters. Therefore, Django should sanitize the input.

----

This was previously reported to the Security Team by rasputinkaiser, however as reason phase is never intended to be user-controlled, it was not considered a vulnerability.

Reported in django ticket #37100: https://code.djangoproject.com/ticket/37100
