# Wrong File object behavior if file object has no name attribute

[https://docs.djangoproject.com/en/1.10/ref/files/file/#the-file-class django.core.files.base.File] supports file-like objects (synonym to file object in python glossary) and in fact can't rely on additional `name` attribute, but in current implementation of `__bool__` method it does:

```
    def __bool__(self):
        return bool(self.name)
```
For example, until `tempfile.SpooledTemporaryFile` isn't large enough to have been written to disk, his `name` attribute is `None` and `if` statement will return False.
```
import tempfile
from django.core.files.base import File
python_file_like_object = tempfile.SpooledTemporaryFile()
file_obj = File(python_file_like_object)  # name keyword is None by default
if file_object:  # Falsy, because python_file_like_object.name is None
    print("42")
```
The same behavior with streams (BytesIO, StringIO).
Maybe `__bool__` method should rely on `self.file` attribute to avoid this behavior?

Reported in django ticket #27150: https://code.djangoproject.com/ticket/27150
