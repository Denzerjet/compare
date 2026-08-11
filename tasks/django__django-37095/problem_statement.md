# URL redirect max length check should check %-encoded value

In #36767 we made configurable the length check on redirect URLs we added for CVE-2025-64458. "Cowork" sent us a flurry of nuisance security reports last night, but among them was a reasonable suggestion that we apply the length check against the percent-encoded URI:

_[a proposed patch was removed from this report]_
Although we didn't take this as a security issue (the limit we apply on the raw value is good enough for DoS), this seems like a functionality bug to fix before the release.

Reported in django ticket #37095: https://code.djangoproject.com/ticket/37095
