# Vary header cache key collision from missing delimiter

When a cached view varies on multiple headers, the values of those headers are concatenated together in the cache key. There is no delimiter, meaning the cache keys could overlap:

```
   X-Region: US
   X-Tenant: victim-corp
```
```
   X-Region: U
   X-Tenant: Svictim-corp
```
The above 2 examples would result in the same cache key, despite being different values. Changes to the cache key should be made to ensure values in this way don't collide.

----

This was previously reported to the Security Team by GeonHa. However, because it requires in depth knowledge of the system, a lack of user validation and similar values, it is not considered a vulnerability.

Reported in django ticket #37101: https://code.djangoproject.com/ticket/37101
