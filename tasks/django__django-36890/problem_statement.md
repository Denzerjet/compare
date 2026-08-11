# Allow providing distinct=True to StringAgg on SQLite by specifying the default delimiter

Attempting to use the new generic StringAgg with distinct=True raises exceptions because any Aggregate with multiple parameters cannot be distinct with an sqlite3 connection. Running StringAgg without distinct produces many duplicate entries aggregated together.

However this Aggregate runs fine under sqlite3, allows distinct and does not produce duplicates.

```
class GroupConcat(Aggregate):
    """Sqlite3 GROUP_CONCAT."""

    # Defaults to " " separator which is all I need for now.

    allow_distinct = True
    allow_order_by = True
    function = "GROUP_CONCAT"
    name = "GroupConcat"

    def __init__(self, *args, **kwargs):
        """output_field is set in the constructor."""
        super().__init__(*args, output_field=CharField(), **kwargs)
```
It occurs to me that this may happen because `delimiter` can be an expression. If delimiter is submitted as some invariant like Value() it would be nice to escape this limitation.

Reported in django ticket #36890: https://code.djangoproject.com/ticket/36890
