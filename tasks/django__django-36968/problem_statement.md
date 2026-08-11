# Provide better error messages when collectstatic can't find a file referenced in another file

At present when `ManifestStaticFilesStorage` finds a reference within a file to another file that does not exist in the static files. It throws an error that causes confusion. For example https://code.djangoproject.com/ticket/21080#comment:43 
Whilenoise has already got a nice pattern to provide a clearer reason to the user so they can fix the issue easily.

    The {ext} file '{filename}' references a file which could not be found: 
    {missing}
    Please check the URL references in this {ext} file, particularly any
    relative paths which might be pointing to the wrong location.

Reported in django ticket #36968: https://code.djangoproject.com/ticket/36968
