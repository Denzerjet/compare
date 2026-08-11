# dumpdata's output of m2m values is not deterministic

Recent failure of `main-random` CI job reveals that dumpdata's output of m2m values is not deterministic:

```
./runtests.py fixtures --shuffle 7825542710 --settings=test_postgres -k forward -v2
```
```
test_forward_reference_fk (fixtures.tests.ForwardReferenceTests.test_forward_reference_fk) ... ok
test_forward_reference_m2m (fixtures.tests.ForwardReferenceTests.test_forward_reference_m2m) ... ok
test_forward_reference_fk_natural_key (fixtures.tests.ForwardReferenceTests.test_forward_reference_fk_natural_key) ... ok
test_forward_reference_m2m_natural_key (fixtures.tests.ForwardReferenceTests.test_forward_reference_m2m_natural_key) ... FAIL

======================================================================
FAIL: test_forward_reference_m2m_natural_key (fixtures.tests.ForwardReferenceTests.test_forward_reference_m2m_natural_key)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/Users/jwalls/django/tests/fixtures/tests.py", line 1308, in test_forward_reference_m2m_natural_key
    self._dumpdata_assert(
    ~~~~~~~~~~~~~~~~~~~~~^
        ["fixtures"],
        ^^^^^^^^^^^^^
    ...<8 lines>...
        natural_foreign_keys=True,
        ^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/jwalls/django/tests/fixtures/tests.py", line 127, in _dumpdata_assert
    self.assertJSONEqual(command_output, output)
    ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: Lists differ: [{'mo[94 chars] [['t3'], ['t2']]}}, {'model': 'fixtures.natur[179 chars][]}}] != [{'mo[94 chars] [['t2'], ['t3']]}}, {'model': 'fixtures.natur[179 chars][]}}]

First differing element 0:
{'mod[49 chars]: 't1', 'other_thing': None, 'other_things': [['t3'], ['t2']]}}
{'mod[49 chars]: 't1', 'other_thing': None, 'other_things': [['t2'], ['t3']]}}

  [{'fields': {'key': 't1',
               'other_thing': None,
-              'other_things': [['t3'], ['t2']]},
?                                     --------

+              'other_things': [['t2'], ['t3']]},
?                               ++++++++

    'model': 'fixtures.naturalkeything'},
   {'fields': {'key': 't2', 'other_thing': None, 'other_things': []},
    'model': 'fixtures.naturalkeything'},
   {'fields': {'key': 't3', 'other_thing': None, 'other_things': []},
    'model': 'fixtures.naturalkeything'}]

----------------------------------------------------------------------
Ran 4 tests in 0.071s

FAILED (failures=1)
Used shuffle seed: 7825542710 (given)
```
----
In the spirit of #24558 and #10381, I'm suggesting to make this deterministic instead of fiddling with the test.

A naive diff just adding ordering by "pk" fixes the failure ...:

_[a proposed patch was removed from this report]_
... but to be mergeable, the patch would need to:
- get the default ordering from somewhere better (through model? target model?), instead of hardcoding "pk"
- check for all locations in the python and xml serializers that might need this change

Reported in django ticket #36750: https://code.djangoproject.com/ticket/36750
