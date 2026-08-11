# Failed deletes in cached_db session backend should log, just like failed writes

The Security Team closed a report about the cached_db session backend, but in so doing, we noticed that we [https://docs.djangoproject.com/en/dev/topics/http/sessions/#:~:text=If%20writing%20to%20the%20cache%20fails%2C%20the%20exception%20is%20handled%20and%20logged%20via%20the%20sessions%20logger%2C%20to%20avoid%20failing%20an%20otherwise%20successful%20write%20operation recently documented] logging any such exceptions for failed writes.

We should handle failed deletes as well, see #34806, which only touched `save()`, not `delete()`. (Starting off as "bug" since the docs imply no save-versus-delete distinction, to my ear.)

Thanks LocalHost for the informative report.

Reported in django ticket #37210: https://code.djangoproject.com/ticket/37210
