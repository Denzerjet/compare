# Add system check for CSP nonce policy without csp context processor

When a project enables `ContentSecurityPolicyMiddleware` and includes `CSP.NONCE` in its policy, but does not configure the `django.template.context_processors.csp` context processor in `TEMPLATES`, the result is a silent security misconfiguration. The developer has the security of a non-nonce policy while believing they have nonce-based protection.

Proposed check:

Register a new security check that emits a Warning (or Error) when all of the following hold:
1. `django.middleware.csp.ContentSecurityPolicyMiddleware` is in the middleware
2. At least one configured policy contains `CSP.NONCE` as a source value
3. No Django template engine in `TEMPLATES` lists `django.template.context_processors.csp`

Possible message:
Your CSP policy includes `CSP.NONCE` and `ContentSecurityPolicyMiddleware` is enabled, but the `django.template.context_processors.csp` context processor is not configured. The nonce will appear in the response header but not in rendered templates, so nonce-based protection will not take effect. Add "django.template.context_processors.csp" to the context_processors option of at least one Django template engine.

Reported in django ticket #37084: https://code.djangoproject.com/ticket/37084
