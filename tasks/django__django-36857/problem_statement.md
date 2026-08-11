# Add totally_ordered property to QuerySet to check for deterministic ordering

Currently, `QuerySet.ordered` returns `True` if any ordering is applied, but this does not guarantee deterministic results. For example, ordering by a non-unique field (like `pub_date`) is considered "ordered", but the relative order of records with the same date is undefined and database-dependent.

This lack of determinism causes issues in pagination and serialization (specifically for natural keys), where a stable sort order is required to ensure consistency.

I propose adding a property (tentatively `totally_ordered`) to `QuerySet` that checks if the applied ordering is sufficient to guarantee a stable sort. This would verify if the order clauses include a unique field (like the primary key) or a set of fields covered by a unique constraint.

Note: Similar logic already exists in `django.contrib.admin.views.main.ChangeList.get_ordering`. The plan is to extract that logic, make it public/reusable on `QuerySet`, and document it.

Context: This feature was identified as a requirement for fixing #36750 (deterministic M2M serialization).

Reported in django ticket #36857: https://code.djangoproject.com/ticket/36857
