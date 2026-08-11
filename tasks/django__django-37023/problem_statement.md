# Make XML serializer put each ManyToManyField object on its own line

The XML serializer serializes many-to-many relations on a single line:

`<field name="categories" rel="ManyToManyRel" to="serializers.category"><object pk="1"></object><object pk="2"></object></field>`

which isn't very readable. I suggest this format instead:

```
<field name="categories" rel="ManyToManyRel" to="serializers.category">
  <object pk="1"></object>
  <object pk="2"></object>
</field>
```
Although not strictly required for this ticket, the first commit in my PR will remove fixed values in the XML serializer's `indent()` calls (e.g. `self.indent(1)`) which are unfriendly to "nested fields" like Django MongoDB Backend's EmbeddedModelField which I'd like to serialize like this:
```
<django-objects version="1.0">
  <object model="serialization_.book">
    <field name="name" type="CharField">Hamlet</field>
    <field name="author" type="EmbeddedModelField">
      <object model="serialization_.author">
        <field name="id" type="ObjectIdAutoField"><None></None></field>
        <field name="name" type="CharField">Shakespeare</field>
        <field name="age" type="IntegerField">55</field>
        <field name="address" type="EmbeddedModelField">
          <object model="serialization_.address">
            <field name="id" type="ObjectIdAutoField"><None></None></field>
            <field name="city" type="CharField">NYC</field>
            <field name="state" type="CharField">NY</field>
            <field name="zip_code" type="IntegerField"><None></None></field>
          </object>
        </field>
      </object>
     </field>
  </object>
</django-objects>
```

Reported in django ticket #37023: https://code.djangoproject.com/ticket/37023
