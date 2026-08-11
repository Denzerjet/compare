# Prevent writing control characters into XML attributes in syndication feeds

The Security Team received a report about constructing a syndication feed item from invalid user input (a control character) breaking an entire feed by causing the XML document to be unparseable.

Control characters other than HT, LF, and CR are not valid in XML. The code path through the XML serializers was adjusted in #20197 to raise a `ValueError` for these characters, but we didn't cover the syndication app, which also uses `SimplerXMLGenerator`.

We closed the report since it involves unsanitized user input, but we could raise a nice `ValueError` (or subclass) to prevent silently writing invalid XML documents.

Thanks sy2n0 for the report.

Reported in django ticket #37183: https://code.djangoproject.com/ticket/37183
