# No-argument form of @sensitive_post_parameters() doesn't cleanse request.POST

The Security Team closed an informative report about the no-argument form of `@sensitive_post_parameters()` not cleansing request.POST, as you can see from adjusting this existing test:

_[a proposed patch was removed from this report]_
```py
AssertionError: 2 != 0 :'sausage-value' unexpectedly found in the following response
```
... but the exception reporter filter is not in-scope for security issues, as filtering is done on a [https://docs.djangoproject.com/en/dev/howto/error-reporting/#filtering-error-reports best-efforts basis].

Looks like an oversight in #21098.

Thanks LocalHost for the report.

Reported in django ticket #37170: https://code.djangoproject.com/ticket/37170
