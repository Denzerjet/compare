# forms.Media shouldn't expect media objects only

While thinking about https://forum.djangoproject.com/t/rejuvenating-vs-deprecating-form-media/21285 I have noticed that the `forms.Media.__add__` method assumes that media objects are only ever added to each other. That doesn't necessarily have to be the case.

I propose returning `NotImplemented` when the RHS isn't a `Media` instance but something else. 

All tests pass locally.

(It has nothing to do with https://code.djangoproject.com/ticket/35648 specifically but the same discussion probably applies.)

Reported in django ticket #36104: https://code.djangoproject.com/ticket/36104
