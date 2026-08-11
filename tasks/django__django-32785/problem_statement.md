# Reduce culling frequency of database cache backend

(Splitting off from: https://code.djangoproject.com/ticket/32772)

== Background

We currently have two settings related to culling caches:

`MAX_ENTRIES` : The number of entries that could go in the cache.

`CULL_FREQUENCY` : The fraction of entries that are culled when MAX_ENTRIES is reached.

(https://docs.djangoproject.com/en/3.2/topics/cache/#cache-arguments)

I run a system with a very large DB cache and I've found that the cache culling code is a bit heavy-handed and slow. Currently, every time you set, add, or touch a cache entry, it runs a cull to make sure that the cache hasn't grown beyond `MAX_ENTRIES`.

The cull triggers a number of queries. Here's an example capturing queries while setting a key:

```
1. SELECT COUNT(*) FROM "test cache table"
2. DELETE FROM "test cache table" WHERE expires < '2021-05-25 00:21:04'
3. SELECT COUNT(*) FROM "test cache table"
4. SELECT cache_key FROM "test cache table" ORDER BY cache_key LIMIT 1 OFFSET 0
5. BEGIN
6. SELECT "cache_key", "expires" FROM "test cache table" WHERE "cache_key" = ':1:force_cull_delete'
7. INSERT INTO "test cache table" ("cache_key", "value", "expires") VALUES (':1:force_cull_delete', 'gAWVCQAAAAAAAACMBXZhbHVllC4=', '2021-05-25 00:37:44')
```
Queries number 1, 2, 3, and 4 are from the culling code. #32772 should eliminate number 3, but there's another query after step 4 that's not shown that could do additional deletions too in some cases. Some of these queries are pretty slow in a cache with a lot of entries (on postgresql, at least). I noticed this issue because the COUNT queries were showing up in my slow query log.


== Proposal

I propose that we don't cull the cache so often. There's two ways to go about it:

1. We just change the functionality so that it culls every so often; we pick a frequency, and we hard code it into the DatabaseCache backend. If people want to change it, they can override the backend.

2. We make a new setting, pick a default for it, and run with that.

One frustrating thing about this is that the current setting for how *much* to cull is called CULL_FREQUENCY instead of something better like CULL_RATIO, so we can't have that variable name. If we went with option two, we'd have to come up with a variable name like CULL_EVERY_X or something. If not for this, I think I'd go for option 2. 

If we do option 1, we avoid that mess, but it splits up the settings for the DB cache between your settings file and your custom backend — but maybe that's fine! I'm happy to implement either approach.

== Other questions

1. I'm agnostic about how to count queries. We could use a random number on each query and then do a mod of it. Something like:

```
random_number = randint(0, CULL_EVERY_X)
if random_number == CULL_EVERY_X:
    cull()
```
Or, sort of equivalently, use a mod on the current time.

Or we could do some sort of counter in the Python code, but that's probably asking for trouble. There's probably a better way here, but I don't know what it is off the top of my head.

2. How do we think about this setting? It could just be a counter: We cull every 20 adds, sets, or touches. Fine. But maybe it makes more sense as a fraction of your MAX_ENTRIES? That'd make it work sort of similarly to CULL_FREQUENCY, which is a percentage of MAX_ENTRIES that are culled whenever a cull is run. So imagine:

MAX_ENTRIES = 1000
CULL_FREQUENCY = 3
CULL_EVERY_X = 5

With those settings, you'd cull down to 667 entries (MAX_ENTRIES - MAX_ENTRIES/CULL_FREQUENCY) when you got to 1,200 entries (MAX_ENTRIES + MAX_ENTRIES/CULL_EVERY_X). 

3. Finally, what's a good default for this? We could take the safe route and cull every query, or move the cheese by changing things in the next release. I vote for the latter, and suggest culling every 1% of MAX_ENTRIES or so by default. I haven't thought about this carefully, but it seems like a good place to begin.

Reported in django ticket #32785: https://code.djangoproject.com/ticket/32785
