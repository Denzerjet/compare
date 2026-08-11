# Make action selection counter on admin list pages announce changes

The admin changelist action counter updates dynamically when selecting or deselecting rows, but the updates are not explicitly announced as live content for assistive technologies.

This can make it harder for screen reader users to perceive selection count changes while performing bulk actions.

Reported in django ticket #36976: https://code.djangoproject.com/ticket/36976
