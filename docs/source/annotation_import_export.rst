
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

This approach is slower as it needs to import each annotation individually,
As a reference, here is a simple python script to import annotations:

.. literalinclude:: examples/import-export-via-import.py

However, depending on the versions of each instances used in a transfert, the `/annotations/import`
route can cause problems. For exemple, if the images are not from the same database or server.
The consequences of these differences can be false negatives (more rejected annotations) to 
outright failure of the whole process.

Instead, you can use the `/annotations/datasets` route. The annotations have to be cleaned beforehand
for this process to work.

Example script for `/annotations/datasets` route
.. literalinclude:: examples/import-export-via-datasets.py

To import annotations from an other source, use `POST` on `/annotations/datasets`. As above, 
will need to login to magpie.

Here is an example:

.. literalinclude:: examples/import-datasets.py
