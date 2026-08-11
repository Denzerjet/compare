# inspectdb doesn't account for normalized field names when building CompositePrimaryKey

inspectdb generates Python model source from database metadata. Most generated metadata already uses repr-style escaping, but two paths still interpolate database-provided values directly into generated source text:

     * composite primary-key column names in models.CompositePrimaryKey(...)
     * table names and exception messages emitted in introspection-error comments

This can produce invalid or unintended generated model code for unusual database schemas containing quotes or newlines.

Reported in django ticket #37203: https://code.djangoproject.com/ticket/37203
