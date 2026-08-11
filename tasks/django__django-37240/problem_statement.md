# simplify_regex() produces corrupted output for URL patterns with multiple unnamed capture groups

`simplify_regex()` re-emits the whole pattern prefix once per capture group, so
any `re_path()` containing **two or more unnamed capture groups** is rendered
with a duplicated, malformed path.

Both callers are affected: the admindocs "Views" page
(`ViewIndexView.get_context_data()` puts `simplify_regex(regex)` straight into
the `url` context value) and the new `listurls` management command added in 6.2.

== Reproduction ==

```python
>>> from django.contrib.admindocs.views import simplify_regex  # django.urls.utils on main
>>> simplify_regex(r'^articles/(\w+)/comments/(\d+)/$')
```
Expected:
```
/articles/<var>/comments/<var>/
```
Actual:
```
/articles/<var>/comments/articles/(\w)/comments/<var>/
```
The corruption compounds with each additional group. With three:

```python
>>> simplify_regex(r'^a/(\w+)/b/(\d+)/c/(\w+)$')
'/a/<var>/b/a/(\w)/b/<var>/c/a/(\w)/b/(\d)/c/<var>'   # expected '/a/<var>/b/<var>/c/<var>'
```
Named groups mixed with unnamed ones are affected too:

```python
>>> simplify_regex(r'^shop/(?P<cat>\w+)/(\w+)/(\d+)/$')
'/shop/<cat>/<var>/shop/<cat>/(\w)/<var>/'            # expected '/shop/<cat>/<var>/<var>/'
```
== End-to-end, via `listurls` on main ==

With this URLconf:

```python
urlpatterns = [
    re_path(r"^articles/(\w+)/comments/(\d+)/$", view),
    re_path(r"^shop/(?P<cat>\w+)/(\w+)/(\d+)/$", view),
    re_path(r"^single/(\w+)/$", view),
]
```
`manage.py listurls -f stacked` prints:

```
Route: /articles/<var>/comments/articles/(\w)/comments/<var>/
Route: /shop/<cat>/<var>/shop/<cat>/(\w)/<var>/
Route: /single/<var>/
```
Only the single-group pattern is correct.

== Affected versions ==

Verified by running the snippet above against released wheels:

|| **Version** || **Output for `^articles/(\w+)/comments/(\d+)/$`** ||
|| 4.2.16 || `/articles/<var>/comments/articles/(\w)/comments/<var>/` ||
|| 5.2.9  || `/articles/<var>/comments/articles/(\w)/comments/<var>/` ||
|| 6.0.7  || `/articles/<var>/comments/articles/(\w)/comments/<var>/` ||
|| main   || `/articles/<var>/comments/articles/(\w)/comments/<var>/` ||

This is long-standing rather than a regression; the same construct is present in
the code that predates both the move of these helpers to `django/urls/utils.py`
in 6.2 and the changes made for #30731.

== Cause ==

In `replace_unnamed_groups()` (`django/urls/utils.py` on main;
`django/contrib/admindocs/utils.py` on 6.0 and earlier):

```python
final_pattern, prev_end = "", None
for start, end, _ignored in _find_groups(pattern, _UNNAMED_GROUP_MATCHER):
    if prev_end:
        final_pattern += pattern[prev_end:start]
    final_pattern += pattern[:start] + "<var>"     # <-- re-emits the prefix
    prev_end = end
return final_pattern + pattern[prev_end:]
```
On the first iteration `prev_end` is `None` and `pattern[:start]` is correct. On
every later iteration the text between the previous group and this one is
appended (correctly), and then `pattern[:start]` appends the entire prefix from
index 0 a second time.

The sibling function `remove_non_capturing_groups()` in the same module already
has the correct shape, relying on `pattern[None:start] == pattern[:start]` for
the first iteration:

```python
final_pattern += pattern[prev_end:start]
```
So the fix collapses the three lines into one that matches the existing idiom:

```python
final_pattern += pattern[prev_end:start] + "<var>"
```
== Why this was never caught ==

`SimplifyRegexTests.test_simplify_regex` (`tests/urlpatterns/tests.py`) has over
100 cases, but **every one of them contains at most one unnamed group**, so
the second-iteration path is never executed.

== Patch ==

PR adds six regression cases covering two and three unnamed groups, unnamed
groups mixed with named ones, nested alternations, and escaped parentheses. All
six fail before the fix and pass after. Full run of `urlpatterns`,
`urlpatterns_reverse`, `admin_docs`, `admin_scripts`, `view_tests` and
`user_commands` is green (733 tests).

A release note is included in `docs/releases/6.0.8.txt` as the fix qualifies for
backport.

Reported in django ticket #37240: https://code.djangoproject.com/ticket/37240
