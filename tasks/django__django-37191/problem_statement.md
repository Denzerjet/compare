# FileBasedCache.touch() raises ValueError: I/O operation on closed file when the key is already expired

FileBasedCache.touch() raises ValueError: I/O operation on closed file when called on a key whose timeout has already elapsed (but whose file hasn't been lazily cleaned up yet).

**Steps to reproduce:**

Use the following settings

```
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/var/tmp/django_cache",
    },
}
```
Run the following (e.g. from the django shell)
```
from django.core.cache import cache

cache.add("key", "value", timeout=1)
time.sleep(2)
cache.touch("key", 60)
```
**Result:** The last `cache.touch` call raises ValueError: I/O operation on closed file

**Expected:** touch() to return False

**Stacktrace:**

```
Traceback (most recent call last):
  File "<console>", line 1, in <module>
  File ".../django_cache_test/.venv/lib/python3.13/site-packages/django/core/cache/backends/filebased.py", line 76, in touch
    locks.unlock(f)
    ~~~~~~~~~~~~^^^
  File ".../django_cache_test/.venv/lib/python3.13/site-packages/django/core/files/locks.py", line 127, in unlock
    fcntl.flock(_fd(f), fcntl.LOCK_UN)
                ~~~^^^
  File ".../django_cache_test/.venv/lib/python3.13/site-packages/django/core/files/locks.py", line 27, in _fd
    return f.fileno() if hasattr(f, "fileno") else f
           ~~~~~~~~^^
ValueError: I/O operation on closed file
```
----


I assume the issue lies in the fileBasedCache class in `django/core/cache/backends/filebased.py`

```
try:
    locks.lock(f, locks.LOCK_EX)
    if self._is_expired(f):
        return False
    else:
        previous_value = pickle.loads(zlib.decompress(f.read()))
        f.seek(0)
        self._write_content(f, timeout, previous_value)
        return True
finally:
    locks.unlock(f)
```
`self._is_expired()` closes the file when it detects that the cache expired and returns False. The finally block is still executed and tries to access the previously closed file.

Reported in django ticket #37191: https://code.djangoproject.com/ticket/37191
