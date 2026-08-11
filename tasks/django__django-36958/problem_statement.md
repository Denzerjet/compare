# Have test client reload logging when logging setting changed

When changing the `LOGGING` setting (eg in tests), `logging` config isn't reconfigured to match.

This can be fairly easily added in a project:

```python
@receiver(setting_changed)
def reload_logging_config(*, setting: str, **kwargs: Any) -> None:
    if setting in {"LOGGING", "LOGGING_CONFIG"}:
        configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)
```
But it would be nice if this was handled by default. This snippet appears to do what I need, but there might be edge cases I've not considered.

Reported in django ticket #36958: https://code.djangoproject.com/ticket/36958
