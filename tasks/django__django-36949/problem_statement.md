# Missing label on each <select> in a fieldset

As Thibaud mentioned [https://github.com/django/django/pull/15317#discussion_r835962239 here] when `use_fieldset` was added to forms, we're lacking a label on each `<select>` element in a `<fieldset>`, even though a `<legend>` is present for the fieldset.

Now that the admin uses `Widget.use_fieldset` since #35892, it's easy to reproduce by just checking a `ForeignKey` field in the admin:

Then, in Chrome Dev Tools, the lighthouse tab reports:

> Select elements do not have associated label elements.


Pure forms reproducer, in a shell:

```py
from django.db import models
from django import forms

class Person(models.Model):
    best_friend = models.ForeignKey(
        "auth.User",
        models.CASCADE,
    )
    class Meta:
        app_label = "myapp.Person"

class MyWidget(forms.Select):
    use_fieldset = True

class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ["best_friend"]
        widgets = {"best_friend": MyWidget}

print(PersonForm().as_p())
```
```py
<p>
    <label for="id_best_friend">Best friend:</label>
    <select name="best_friend" required id="id_best_friend">
  <option value="" selected>---------</option>

  <option value="2">anonymous</option>

  <option value="1">admin</option>

</select>
    
    
      
    
  </p>
```
----
Tentatively assigning to Eli as a Djangonaut Space navigator to evaluate if a good fit for anyone.

Reported in django ticket #36949: https://code.djangoproject.com/ticket/36949
