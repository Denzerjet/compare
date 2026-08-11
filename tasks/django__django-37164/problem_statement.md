# Support jsonl Deserializer subclasses' _get_lines methods

The jsonl `Deserializer` class calls `Deserializer._get_lines()` directly, rather than via `self`, preventing subclasses from overriding this methods (for example, to use an alternative JSON library). This has been the case since ee5147cfd7de2add74a285537a8968ec074e70cd. Let's change it to use `self`.

Reported in django ticket #37164: https://code.djangoproject.com/ticket/37164
