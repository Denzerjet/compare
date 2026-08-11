# Prevent extremely long validation messages in inlines

Currently Django inlines generate a DeleteProtectedModelForm with `hand_clean_DELETE` that validates for protected items. If the amount of protected items is large, the error message is huge as all protected objects are listed. The message spanning thousands of entries is impossible to read as is not structured, and nobody is going to check thousands of items manually either. An image showing what it looks like (excuse my locale of the message): [[Image(https://ibb.co/4RKCK5Nb)]]

Therefore, I propose to limit the amount of protected items shown in inline validation, listing at most N items where N is subject to a discussion, and then adding "and X more" to indicate that the list is not extensive.

Here is a rough idea on how this could be implemented:

```
def hand_clean_DELETE(self):
    """
    We don't validate the 'DELETE' field itself because on
    templates it's not rendered using the field information, but
    just using a generic "deletion_field" of the InlineModelAdmin.
    """
    if self.cleaned_data.get(DELETION_FIELD_NAME, False):
        using = router.db_for_write(self._meta.model)
        collector = NestedObjects(using=using)
        if self.instance._state.adding:
            return
        collector.collect([self.instance])
        if collector.protected:
            objs = []
            for p in collector.protected[:MAX_VALIDATION_OUTPUT_ITEMS]:
                objs.append(
                    # Translators: Model verbose name and instance
                    # representation, suitable to be an item in a
                    # list.
                    _("%(class_name)s %(instance)s")
                    % {"class_name": p._meta.verbose_name, "instance": p}
                )
            params = {
                "class_name": self._meta.model._meta.verbose_name,
                "instance": self.instance,
            }
            if len(collector.protected) > MAX_VALIDATION_OUTPUT_ITEMS:
                params['related_objects'] = get_text_list(objs, _(", ")) + _(' and %d more') % (len(collector.protected) - MAX_VALIDATION_OUTPUT_ITEMS)
            else:
                params['related_objects'] = get_text_list(objs, _(" and "))
            msg = _(
                "Deleting %(class_name)s %(instance)s would require "
                "deleting the following protected related objects: "
                "%(related_objects)s"
            )
            raise ValidationError(
                msg, code="deleting_protected", params=params
            )
```
If everyone is happy about this, I could implement the change.

Reported in django ticket #36984: https://code.djangoproject.com/ticket/36984
