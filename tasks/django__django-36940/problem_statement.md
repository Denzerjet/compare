# Improve ASGI script prefix path_info handling

The current ASGIRequest.__init__ uses str.removeprefix() to strip the script name from the request path to compute path_info. This is fragile because removeprefix is a pure string operation — it doesn't verify that the prefix is a proper path segment boundary.

For example, if script_name is /myapp and the path is /myapplication/page, removeprefix would incorrectly produce lication/page.

This patch replaces removeprefix with a check that ensures the script name is followed by / or is the exact path, before stripping it. This addresses the inline TODO comment.

Reported in django ticket #36940: https://code.djangoproject.com/ticket/36940
