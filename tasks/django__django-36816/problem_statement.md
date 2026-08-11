# Allow **kwargs in @task decorator to support custom Task subclasses

Currently, the @task decorator accepts a fixed set of parameters and passes only those to task_class:


Problem: When using a custom backend with a custom task_class that accepts additional parameters (e.g., max_retries, timeout), there's no way to pass those through the decorator.

```
def task(
    function=None,
    *,
    priority=DEFAULT_TASK_PRIORITY,
    queue_name=DEFAULT_TASK_QUEUE_NAME,
    backend=DEFAULT_TASK_BACKEND_ALIAS,
    takes_context=False,
):
    # ...
    return task_backends[backend].task_class(
        priority=priority,
        func=f,
        queue_name=queue_name,
        backend=backend,
        takes_context=takes_context,
        run_after=None
    )

```
Proposed solution: Add **kwargs to the decorator signature and pass it through to task_class:
```
def task(
    function=None,
    *,
    priority=DEFAULT_TASK_PRIORITY,
    queue_name=DEFAULT_TASK_QUEUE_NAME,
    backend=DEFAULT_TASK_BACKEND_ALIAS,
    takes_context=False,
    **kwargs,
):
    def wrapper(f):
        return task_backends[backend].task_class(
            priority=priority,
            func=f,
            queue_name=queue_name,
            backend=backend,
            takes_context=takes_context,
            run_after=None,
            **kwargs,
        )
    
```
Use case example:

```
class MyTask(Task):
    def __init__(self, *, max_retries=3, timeout=300, **kwargs):
        super().__init__(**kwargs)
        self.max_retries = max_retries
        self.timeout = timeout

# With the proposed change:
@task(backend="my_backend", max_retries=5, timeout=600)
def my_task():
    pass
```
This change is backwards compatible and aligns with Django's common extensibility patterns.

Reported in django ticket #36816: https://code.djangoproject.com/ticket/36816
