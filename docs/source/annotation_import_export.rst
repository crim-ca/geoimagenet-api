
***********************************
Importing and exporting annotations
***********************************

It is possible to transfer annotations from one deployed instance to another.
You have to export, and import the annotations. The file format to do the transfer
is GeoJson.

To export annotations, use `GET` on `/annotations`. Refer to the api documentation
to see filters you can use. You might have to login to magpie to do so.

To import annotations, use `POST` on `/annotations/import`. Again, you might have to
login to magpie on the other platform. The properties for the imported annotations
will be as followed:

 - The user id will be the one of the currently logged user in the platform where the
   import takes place
 - The status property will be the one provided in the annotation properties, as opposed to
   being forced to `new` for the regular POST on `/annotations`
 - The review_requested flag will behave in the same way as the status property

As a reference, here is a simple python script to import annotations:

.. literalinclude:: examples/import-export.py

To import annotations from an other source, use `POST` on `/annotations/datasets`. As above, 
will need to login to magpie.

Here is an example:

.. literalinclude:: examples/import-datasets.py
