# Admin inline with view permission is shown when save_as validation fails

How to reproduce:

Make a modeladmin with save_as=True, and one unique field, with an inline where the user only has 'view' permission.

Create an instance. Open it, press "save as new". 

This will result in the validation error, as it should, but the inline is shown as editable with empty forms. The number of forms corresponds to the number of inline forms.

If the unique field is changed, even if the data is entered in the inline form, nothing is saved (so there is no security issue, it just looks bad).

Reported in django ticket #29969: https://code.djangoproject.com/ticket/29969
