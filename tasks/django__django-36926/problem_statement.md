# Admin list_display does not use boolean icons when traversing relations

I have a UserProfile model that I am attempting to inline into the User admin page.

I want to show an additional column in the User admin denoting the value of UserProfile.verified. I can successfully add this column by appending `'profile__verified'` the list_display property of my custom UserAdmin class, however the value that shows up in the column is either the string `"True"` or `"False"`.

It would be great if adding `'profile__verified'` to the list_display of the admin class could detect that the field is a boolean (it is indeed an instance of `models.BooleanField` on the `UserProfile`), and display the icons.

My current workaround is to define a callable on my custom admin class and mark it as a boolean with the `admin.display` decorator.

For reference, here is the model and admin class that produce the undesirable behavior:

```
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    verified = models.BooleanField(default=False)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_select_related = ['profile']

    list_display = list(BaseUserAdmin.list_display) + ['profile__verified']
    list_filter = list(BaseUserAdmin.list_filter) + ['profile__verified']
```

Reported in django ticket #36926: https://code.djangoproject.com/ticket/36926
