# BaseModelFormSet could leverage totally_ordered property

#36857 added a new property `totally_ordered` on `QuerySet` to capture the difference between a queryset having ''some'' ordering versus a "stable, deterministic" ordering.

I noticed that we probably want to use that new property here in `BaseModelFormSet` for the purpose described in #10163:

_[a proposed patch was removed from this report]_
Tentatively assigning to Sarah to see if a good fit for any Djangonauts this session. This would involve cooking up a test.

Reported in django ticket #37004: https://code.djangoproject.com/ticket/37004
