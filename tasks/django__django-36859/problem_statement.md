# SimpleTestCase.assertContains can't be called multiple times on a streaming response

I recently got an unexpected test failure when using `SimpleTestCase.assertContains()`:

```python
def test_some_view(self):
    response = self.client.get("/some/url/")
    self.assertContains(response, "something")
    self.assertContains(response, "another thing")  # This failed
```
Even though my view at `/some/url/` was returning a response that did include both `"something"` and `"another thing"`, the test was failing on the second assertion. After some confusion, I eventually figured out that the cause of this failure was that the view was returning a `StreamingHttpResponse`.

This failure makes sense if you understand the internals of streaming responses, but I'd argue that the test code shouldn't have to care about the nature of the response, and that repeated calls to `assertContains` should work transparently.

As far as I can tell, this behavior is not documented (one way or another) and has always been present (see 82b3e6ffcb9d810cc0e3ec27d25f89ce1fd525e0).

(PR with test case and tentative fix will be attached to this ticket soon)

Reported in django ticket #36859: https://code.djangoproject.com/ticket/36859
