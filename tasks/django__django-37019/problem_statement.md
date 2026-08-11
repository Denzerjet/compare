# Make sync login() and logout() set request.auser if present

Analogous to #37017, we should make sync `logout()` clear `request.auser` if present. If `auser` is not present, I doubt `login()` should set it, but if it is present, it probably should be set as well.

Reported in django ticket #37019: https://code.djangoproject.com/ticket/37019
