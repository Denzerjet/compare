# Add multipart_parser_class attribute to HttpRequest for pluggable multipart parsing

== Problem

Django's `parse_file_upload()` hardcodes `MultiPartParser`, making it hard 
to swap in faster implementations.

== Proposed Solution

As discussed with the steering council and Carlton Gibson on the forum:

1. Add `multipart_parser_class` class attribute to `HttpRequest` (defaulting to `MultiPartParser`)

2. Modify `parse_file_upload()` to use `self.multipart_parser_class` instead of direct import

3. Ensure uniform parser interface: `__init__(META, input_data, upload_handlers, encoding)` 
   with `parse()` returning `(POST, FILES)`

== Usage

Users can subclass `HttpRequest` and override `multipart_parser_class` to use 
faster parsers.

== Benefits

- Immediate performance improvements for those who need them
- Stepping stone toward DEP 17 https://github.com/django/deps/pull/88 (pluggable content type parsers)
- Minimal change
- Follows proven pattern from Django REST Framework's `parser_classes`

== Forum Discussion
https://github.com/django/new-features/issues/105

Reported in django ticket #36841: https://code.djangoproject.com/ticket/36841
