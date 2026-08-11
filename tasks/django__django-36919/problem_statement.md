# Allow `TaskResult` to be pickled

As part of implementing some task backends, it can be useful to pickle a `TaskResult` to pass it around implementation.

Since it's a `dataclass` most of the implementation is already there - the main issue is that `Task` itself can't be pickled as it references a function. Replacing that with a string reference during pickling will likely resolve the current issues.

The implementation isn't especially complex, so I'm not opposed to this being closed and left to backend implementers to deal with instead.

Reported in django ticket #36919: https://code.djangoproject.com/ticket/36919
