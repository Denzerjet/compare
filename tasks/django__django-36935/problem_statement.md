# ContentType.app_labeled_name fallback omits app label when model_class() is None

= ContentType.app_labeled_name fallback omits app label when model_class() is None =

== Environment ==

 * Django version: 5.0 (also reproduced on latest `main` as of 2026‑02‑18)
 * Python: 3.x
 * Database: Oracle (others likely affected)

== Summary ==

`django.contrib.contenttypes.models.ContentType.app_labeled_name` is intended to provide a human‑readable label combining the app label and model name, typically used in admin UIs and other tooling to disambiguate models with the same name.

Its current implementation is roughly:

```
@property
def app_labeled_name(self):
    model = self.model_class()
    if not model:
        return self.model
    return '%s | %s' % (model._meta.app_label, model._meta.verbose_name)
```
When `model_class()` returns a model, this works as expected and returns:

```
<app_label> | <model verbose_name>
```
However, when `model_class()` returns `None` (for example, for stale or external content types), the property falls back to returning only `self.model`, which drops the app label and makes the label ambiguous. In projects with many apps, this makes it hard to distinguish entries that share the same model name. It is also inconsistent with the name *app_labeled_name*, which suggests that the app label is always present.

This degraded behaviour can be seen in admin UI elements or APIs that rely on `app_labeled_name` when the underlying content type cannot be resolved to a concrete model.

== Steps to reproduce ==

 1. Create a `ContentType` whose model cannot be resolved in the current project (for example, by creating a content type for an app/model that is no longer installed, or by inserting a row with a bogus model name).
 2. In a Django shell, access that instance’s `app_labeled_name`.
 3. Use that `ContentType` in any UI or API that displays `app_labeled_name` (for example, a custom admin widget or permission management screen).

Example (simplified):

```
from django.contrib.contenttypes.models import ContentType

ct = ContentType.objects.create(
    app_label='external_app',
    model='externalmodel',
)

ct.model_class()      # returns None
ct.app_labeled_name  # returns 'externalmodel'
```
== Actual behavior ==

For content types whose `model_class()` is `None`, `app_labeled_name` returns only the raw model string:

```
'externalmodel'
```
The app label is omitted, which makes the label ambiguous in UIs that list many models from many apps.

== Expected behavior ==

Even when `model_class()` is `None`, `app_labeled_name` should still include the app label so that the label remains informative and consistent with its name. A more helpful and still backwards‑compatible fallback would be:

```
@property
def app_labeled_name(self):
    model = self.model_class()
    if not model:
        return '%s | %s' % (self.app_label, self.model)
    return '%s | %s' % (model._meta.app_label, model._meta.verbose_name)
```
This keeps the current behaviour when the model exists (using the translated `verbose_name`) and improves the fallback when it does not, by returning:

```
'external_app | externalmodel'
```
This matches the intent of ticket #16027 (Include app_label in ContentType.^^_^^_str^^_^^_()) to disambiguate models with the same name by always including the app label.

== Rationale / backwards compatibility ==

 * For existing, valid content types (`model_class()` not `None`), behaviour is unchanged.
 * For invalid/stale/external content types, behaviour becomes *more* informative; currently they return just the model name, which is rarely desirable in user‑facing lists.
 * The change is therefore backwards compatible and strictly improves the degraded code path.

== Possible patch ==

If this proposal is accepted, a patch could:

 * Update `ContentType.app_labeled_name` as shown above.
 * Add tests for both cases:
   * A content type with a real model (assert the current behaviour is preserved).
   * A content type whose `model_class()` is `None` (assert that `app_labeled_name` returns `'app_label | model'`).

I’m happy to submit a pull request with implementation and tests once there is agreement on the desired behaviour.

Reported in django ticket #36935: https://code.djangoproject.com/ticket/36935
