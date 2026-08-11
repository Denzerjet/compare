# edge case: django.test.client should handle fields and files with the same name

problem:
- want to upload file with very common name, e.g. 'somefield'
- want to post data with very common name for field, e.g. 'somefield'

http://www.scotthawker.com/scott/?p=1892

http://code.activestate.com/recipes/146306/

```
>>> fields = { 'somefield': 1 }
>>> files = { 'somefield': open('/dev/null', 'r') }
>>> data = QueryDict('', mutable=True)
>>> data.update(fields)
>>> data.update(files)
>>> data
<QueryDict: {u'somefield': [1, <open file '/dev/null', mode 'r' at 0x8a0c610>]}>
>>> data.items()
[(u'somefield', <open file '/dev/null', mode 'r' at 0x8a0c610>)]
>>> data
<QueryDict: {u'somefield': [1, <open file '/dev/null', mode 'r' at 0x8a0c610>]}>
>>> 
>>> from django.utils.datastructures import MultiValueDict
>>> data = MultiValueDict()
>>> data.update(fields)
>>> data.update(files)
>>> data
<MultiValueDict: {'somefield': [1, <open file '/dev/null', mode 'r' at 0x8a0c610>]}>
>>> data.items()
[('somefield', <open file '/dev/null', mode 'r' at 0x8a0c610>)]
>>> data['somefield']
<open file '/dev/null', mode 'r' at 0x8a0c610>
>>> data.getlist('somefield')
[1, <open file '/dev/null', mode 'r' at 0x8a0c610>]
>>> 
```
https://code.djangoproject.com/browser/django/trunk/django/test/client.py

```
116	    # Each bit of the multipart form data could be either a form value or a
117	    # file, or a *list* of form values and/or files. Remember that HTTP field
118	    # names can be duplicated!
119	    for (key, value) in data.items():
```
IMHO, the test client should use data.lists() instead when providing MultiValueDict or subclass.

Reported in django ticket #17631: https://code.djangoproject.com/ticket/17631
