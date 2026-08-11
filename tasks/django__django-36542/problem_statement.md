# AdminSite views (such as login) leak sensitive POST data

Hey !

Recently I came accross plain text user passwords in debug reports when there is an exception on the login view. Such exceptions can happen very easily in many basic scenarios such as an unreachable database. The passwords are visible in:

1/ regular debug reports when DEBUG=True

https://code.djangoproject.com/attachment/ticket/36542/image.png

2/ email reports when DEBUG=False and include_html=True

https://code.djangoproject.com/attachment/ticket/36542/image%20(1).png

I reported this to the security team, but quite reasonably they decided it's not a security issue since it's very clear no one should use DEBUG=True in PROD (and there, users would just see their own password anyway), and that the docs already warn quite a bit against enabling "include_html" in email reports. Yet they agreed this is still worth improving.

For context, Django already redacts much less critical infos by default in the report such as the csrftoken or internal settings, even if these are harder to exploit and unlike user passwords usually already known to admins. Having such info redacted gives some false sense of security about these reports.

I didn't test but think there are other cases in django core such as user creation forms (password1, password2) or password changes (old_password, new_password1, new_password2), and of course this would also happen in third party apps / user code.

In terms of fixing this, why don't we just apply the same filter used for settings (`API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE`) to POST parameters as well as variables in the full trace ? I feel this would cover most cases and be quite straightforward to implement and to understand for users. For that matter, better to redact too many variables than too few.

Cheers !

Reported in django ticket #36542: https://code.djangoproject.com/ticket/36542
