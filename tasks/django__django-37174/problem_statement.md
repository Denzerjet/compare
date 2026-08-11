# Template fragment cache key collision for vary_on values containing ":"

The [https://docs.djangoproject.com/en/6.0/topics/cache/#template-fragment-caching documented example] for template fragment caching demonstrates using `request.user.username` as a `vary_on` argument. If that username contained `:`, and another `vary_on` argument was present, then two cache keys might collide, and the wrong content could be served.

See this PoC provided to the Security Team:

```py
from django.core.cache.utils import make_template_fragment_key
a = make_template_fragment_key("frag", ["alice", "b:c"])
b = make_template_fragment_key("frag", ["alice:b", "c"])
assert a == b   # same key
```
We decided against accepting this as a security issue given the unlikelihood of colons in the data most important to vary on from a security perspective, e.g. usernames in a ''username'' + ''language code'' vary_on pair, but there is a correctness issue to fix here.

One fix strategy would involve incorporating the lengths of the arguments into the cache key.

Since this will cause cache busting, we should probably document in the release note something similar to the note from 5cb3ed187b283059589cb442c56a66a795800cac.

Reported in django ticket #37174: https://code.djangoproject.com/ticket/37174
