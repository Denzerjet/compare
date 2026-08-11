# collectstatic post-processing fails for references inside comments

"python manage.py collectstatic" is attempting to parse references inside css comments and generating errors during post-processing. I am using:
`STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.CachedStaticFilesStorage'`


eg.
The following snippet of code in test.css:

```
.gfg-collapse-closed {
  /* background-image : url('arrow_close.gif'); */
}

```
produces the following error:
```
ValueError: The file 'stylesheets/arrow_close.gif' could not be found with <django.contrib.staticfiles.storage.CachedStaticFilesStorage object at 0x1078a3910>.
collectstatic

```
Ideally, collectstatic should respect CSS comments and should not attempt to parse/reference files in lines that are commented out.

If the fix is too complex, a simple workaround might be to include a `--ignore-error` flag that would allow the application to continue post-processing even when it sees errors

Reported in django ticket #21080: https://code.djangoproject.com/ticket/21080
