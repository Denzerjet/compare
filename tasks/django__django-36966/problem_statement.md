# Test client using query_params raises ValueError when following redirect

When the test client is called with `query_params` and `follow=True`, a `ValueError` is raised when following the redirect.                                                                                                 
                  
`_follow_redirect` populates `data` from the redirect URL's query string via `QueryDict(url.query)`. Since `query_params` from the original request is never reset, both `data` and `query_params` end up non-empty, triggering: `ValueError: query_params and data arguments are mutually exclusive.`

Ref: https://github.com/django/django/blob/35dab0ad9ee2ed23101420cb0f253deda2818191/django/test/client.py#L998

== Reproduction ==

  `
  def test_follow_redirect_with_query_params(self):
      self.client.get("/redirect_view/", query_params={"next": "x"}, follow=True)  # this yells
  `

Reported in django ticket #36966: https://code.djangoproject.com/ticket/36966
