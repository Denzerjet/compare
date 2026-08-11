# ASGI: Dead persistent postgres connections are not closed when the database is accessed in response_for_exception

This problem is similar to ticket:31905

How to reproduce:

1. Create a 404 or other exception template that use a db connection.
2. Make a first request to a url that return for example a 404. 
3. Restart your db server, forcing connections to be closed.
4. Visit again the same url and you will receive the error "the connection is closed".

Traceback:

```
 File "django/core/handlers/exception.py", line 42, in inner
    response = await get_response(request)
  File "django/core/handlers/base.py", line 235, in _get_response_async
    callback, callback_args, callback_kwargs = self.resolve_request(request)
  File "django/core/handlers/base.py", line 313, in resolve_request
    resolver_match = resolver.resolve(request.path_info)
  File "django/urls/resolvers.py", line 705, in resolve
    raise Resolver404({"tried": tried, "path": new_path})
OperationalError: the connection is closed
  File "django/db/backends/base/base.py", line 298, in _cursor
    return self._prepare_cursor(self.create_cursor(name))
  File "django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
  File "django/db/backends/postgresql/base.py", line 429, in create_cursor
    cursor = self.connection.cursor()
  File "psycopg/connection.py", line 213, in cursor
    self._check_connection_ok()
  File "psycopg/_connection_base.py", line 524, in _check_connection_ok
    raise e.OperationalError("the connection is closed")
OperationalError: the connection is closed
  File "django/core/handlers/exception.py", line 164, in get_exception_response
    response = callback(request, exception=exception)
  File "django/utils/decorators.py", line 188, in _view_wrapper
    result = _process_exception(request, e)
  File "django/utils/decorators.py", line 186, in _view_wrapper
    response = view_func(request, *args, **kwargs)
  File "django/views/defaults.py", line 64, in page_not_found
    body = template.render(context, request)
  File "django/template/backends/django.py", line 107, in render
    return self.template.render(context)
  File "django/template/base.py", line 169, in render
    with context.bind_template(self):
  File "contextlib.py", line 137, in __enter__
    return next(self.gen)
  File "django/template/context.py", line 256, in bind_template
    context = processor(self.request)
  File "core/context_processors.py", line 15, in global_settings
    site_settings = SiteSettings.get_instance(request=request)
  File "core/models.py", line 180, in get_instance
    return SiteSettings.for_request(request)
  File "wagtail/contrib/settings/models.py", line 127, in for_request
    site = Site.find_for_request(request)
  File "wagtail/models/sites.py", line 157, in find_for_request
    site = Site._find_for_request(request)
  File "wagtail/models/sites.py", line 167, in _find_for_request
    site = get_site_for_hostname(hostname, port)
  File "wagtail/models/sites.py", line 23, in get_site_for_hostname
    sites = list(
  File "django/db/models/query.py", line 400, in __iter__
    self._fetch_all()
  File "django/db/models/query.py", line 1928, in _fetch_all
    self._result_cache = list(self._iterable_class(self))
  File "django/db/models/query.py", line 91, in __iter__
    results = compiler.execute_sql(
  File "django/db/models/sql/compiler.py", line 1572, in execute_sql
    cursor = self.connection.cursor()
  File "django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
  File "django/db/backends/base/base.py", line 320, in cursor
    return self._cursor()
  File "django/db/backends/base/base.py", line 297, in _cursor
    with self.wrap_database_errors:
  File "django/db/utils.py", line 91, in __exit__
    raise dj_exc_value.with_traceback(traceback) from exc_value
  File "django/db/backends/base/base.py", line 298, in _cursor
    return self._prepare_cursor(self.create_cursor(name))
  File "django/utils/asyncio.py", line 26, in inner
    return func(*args, **kwargs)
  File "django/db/backends/postgresql/base.py", line 429, in create_cursor
    cursor = self.connection.cursor()
  File "psycopg/connection.py", line 213, in cursor
    self._check_connection_ok()
  File "psycopg/_connection_base.py", line 524, in _check_connection_ok
    raise e.OperationalError("the connection is closed")
```
This problem could be solved, removing the argument **thread_sensitive** from **sync_to_async** in **convert_exception_to_response** function [[https://github.com/django/django/blob/f05edb2b43c347d4929efd52c8e2b4e08839f542/django/core/handlers/exception.py#L45|Link to Repo File]]. 

With this change, the thread used will be the same of the outer task, where the connections were already checked in request_start signal by close_old_connections.

Reported in django ticket #36027: https://code.djangoproject.com/ticket/36027
