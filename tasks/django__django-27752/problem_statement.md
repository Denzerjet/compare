# Fix and test admin_order_field set for the __str__ of a model

While doing some force_str cleanup on Django 2.0, Tim Graham and me noticed a possible issue with `admin_order_field` on a `__str__`method (in `django.contrib.admin.utils.label_for_field`). It's apparently untested. See this related commit [1], with a test that was later removed [2].

https://github.com/django/django/commit/2304ca423640a7b06390530bf61c879f9ff9e4ba
https://github.com/django/django/commit/65cc646c4801e3f3e1df1ab06dfaa763fa4b7b22

So a test for the proper label and sorting is wanted. See `test_change_list_sorting_model_admin` in `tests/admin_views/tests.py` for a similar test.

Reported in django ticket #27752: https://code.djangoproject.com/ticket/27752
