# Admin change form actions should only allow applying to object from the change form

We had a few security reports against the new admin change form action feature that a user could tamper with the `_selected_action` value and then run the action against a different object, with concerns that the same user may not be able to view or change that admin object.

I think a `BadRequest` should be raised if the `_selected_action` value does not match the url it was sent from

_[a proposed patch was removed from this report]_

Reported in django ticket #37105: https://code.djangoproject.com/ticket/37105
