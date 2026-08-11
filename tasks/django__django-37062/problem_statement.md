# Add `preserve_request` support to `RedirectView`

The `redirect` shortcut supports `preserve_request` to maintain the method and body of the original request during redirect. 

The same functionality should exist on `RedirectView` to enable the same behaviour. Both as a class-level attribute and argument to `as_view`.

Reported in django ticket #37062: https://code.djangoproject.com/ticket/37062
