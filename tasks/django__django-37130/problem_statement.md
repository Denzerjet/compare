# Unnecessary query in db cache backend when CULL_FREQUENCY > MAX_ENTRIES + 1

The db cache backend deletes expired entries according to a `CULL_FREQUENCY` denominator after expired entries are deleted. For example: `2`, means delete 50%. This generates SQL like:

```sql
SELECT cache_key from ... ORDER_BY cache_key LIMIT 1 OFFSET N
DELETE FROM ... WHERE cache_key < result of query 1
```
But where N is 0 (`cull_num` in the code), the SELECT is unnecessary. I'm suggesting there should be another fast path where `cull_num` is 0 that simply exits.

I spotted this in a real user's logs, see #32785.

This would happen when `CULL_FREQUENCY` > `MAX_ENTRIES` + 1. I imagine the use cases for that configuration would be:
- a culling strategy that is age-based instead of random, see [https://forum.djangoproject.com/t/django-database-cache-untouched-expired-entries-are-never-culled-unless-max-entries-is-reached/22679 forum]
- in tests, overriding `MAX_ENTRIES` to 0 or 1 for determinism, which would then fall below the default `CULL_FREQUENCY` of 3.

Reported in django ticket #37130: https://code.djangoproject.com/ticket/37130
