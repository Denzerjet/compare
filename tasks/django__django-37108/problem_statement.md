# DjangoJSONEncoder encodes time inconsistently depending on microseconds

Consider this script:

```
import json
from datetime import datetime, time, UTC
from django.core.serializers.json import DjangoJSONEncoder

print(json.dumps(datetime.fromtimestamp(0, UTC), cls=DjangoJSONEncoder))
print(json.dumps(datetime.fromtimestamp(0.000001, UTC), cls=DjangoJSONEncoder))

print(json.dumps(time(), cls=DjangoJSONEncoder))
print(json.dumps(time(microsecond=1), cls=DjangoJSONEncoder))
```
It outputs the following:

```
"1970-01-01T00:00:00Z"
"1970-01-01T00:00:00.000Z"
"00:00:00"
"00:00:00.000"
```
In other words, even though the encoded value is logically the same, `DjangoJSONEncoder` either adds ".000" or doesn't depending on the number of microseconds.

This is not a big problem, but it is mildly annoying. Imagine you save a fixture with `dumpdata`, load it back, then save again. The first time, the encoder adds ".000", then after loading the number of microseconds is set to 0, so after the second save, the encoder ''doesn't'' add ".000". Now there's an unnecessary change in the saved fixture.

Seems like the encoder should either always add ".000" or always omit it.

Reported in django ticket #37108: https://code.djangoproject.com/ticket/37108
