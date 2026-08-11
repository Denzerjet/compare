# Allow overriding redirect URL max length in `HttpResponseRedirectBase`

Redirect URLs can legitimately get very large depending on the application. For example, S3 presigned URLs, signed download links, or OAuth/SSO protocols that stuff state, nonces, or signatures into the query string. Django currently enforces a hardcoded `MAX_URL_REDIRECT_LENGTH` (introduced in 880530ddd4fabd5939bab0e148bebe36699432a and a8cf8c292cfee98fe6cc873ca5221935f1d02271). This means fully valid URLs from these workflows may end up raising `DisallowedRedirect`, even though long redirect targets are perfectly fine in HTTP.

I think we need to make the limit overridable, similarly to what was done in #35784. A simple approach would be to extend `HttpResponseRedirectBase` to accept an optional `max_length` argument. If provided, it overrides the default. If set to `None`, the check is disabled altogether. The current default stays in place for safety.

This gives projects a documented and explicit escape hatch without changing the default behavior. And it is worth calling out that long redirect URLs have no performance impact on Django itself on non-Windows platforms. The original limit was mainly about avoiding unicode normalization costs in Python's URL parsing on Windows, which is not the common deployment case according to our usage surveys.

There is an initial patch that adds the parameter, updates the checks accordingly, and adds tests. It needs some refinement and docs, but the approach seems sound.

Reported in django ticket #36767: https://code.djangoproject.com/ticket/36767
