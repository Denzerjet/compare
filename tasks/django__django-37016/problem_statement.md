# Avoid propagating invalid arguments from When() to Q() on dictionary expansion

The Security Team just closed a report extrapolating from 279f8b9557f0fef9790822b0c38164fc9dfcab2a arguing that `When()` is missing the same protection we gave to `filter()` and friends, whereby we raise errors for the `_connector` and `_negated` arguments instead of passing them down to `Q()`, like this:

```py
    def _filter_or_exclude_inplace(self, negate, args, kwargs):
        if invalid_kwargs := PROHIBITED_FILTER_KWARGS.intersection(kwargs):
            invalid_kwargs_str = ", ".join(f"'{k}'" for k in sorted(invalid_kwargs))
            raise TypeError(f"The following kwargs are invalid: {invalid_kwargs_str}")
```
We don't consider this a vulnerability, as we didn't even consider 279f8b9557f0fef9790822b0c38164fc9dfcab2a a vulnerability, just an incidental finding we shipped with the security releases (notice the commit message says "Refs ..." not "Fixed ...") and thought prudent to backport. (The crux of the CVE was the arbitrary SQL injection, not a query logic bug downstream of a user's failure to validate user inputs.)

Still, we would welcome a PR to django's main branch that extends the protection quoted above to `When()`.

Thanks m0_ld for the report.

Reported in django ticket #37016: https://code.djangoproject.com/ticket/37016
