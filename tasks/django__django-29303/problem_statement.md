# non_atomic_requests decorator alters _non_atomic_requests attribute of original function

When calling `non_atomic_requests` with a function, it alters the `_non_atomic_requests` attribute of the original function.

Here's an example:

```
from django.test import TestCase

# Create your tests here.

from django.test import TestCase
from django.db import transaction

@transaction.non_atomic_requests(using='default')
def my_view(request):
        return HttpResponse('')

class TestViews(TestCase):

    def test(self):
        assert my_view._non_atomic_requests == {'default'}  # passes

        wrapped_view = transaction.non_atomic_requests(using='other')(my_view)

        assert wrapped_view._non_atomic_requests == {'default', 'other'}  # passes
        assert my_view._non_atomic_requests == {'default'}  # fails
```
I realise that this is a contrived example. It isn't an issue when `non_atomic_requests` is used as a decorator:

```
@transaction.non_atomic_requests(using='default')
@transaction.non_atomic_requests(using='other')
def my_view(request)
    return HttpResponse('')
```

Reported in django ticket #29303: https://code.djangoproject.com/ticket/29303
