# GZipMiddleware buffers streaming responses

This ticket proposes adding a test to confirm that `compress_sequence()`
in `django.utils.text` correctly flushes each chunk during gzip streaming.

The absence of `zfile.flush()` would cause compressed output to be buffered,
delaying response delivery in streaming contexts. This test uses timed
chunk generation to verify that data is emitted approximately once per second,
indicating that gzip output is non-blocking when `flush()` is used.

See related PR: https://github.com/django/django/pull/19335

Reported in django ticket #36293: https://code.djangoproject.com/ticket/36293
