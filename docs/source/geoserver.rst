.. _geoserver-configuration:

***********************
Geoserver configuration
***********************

The GeoServer datastore and cascading WMS instances can be configured with a cli utility.

It is important that the raster images are configured with this command line, as some
important parameters are set by the cli (bounding boxes, keywords, etc.)

.. click:: geoimagenet_api.geoserver_setup.main:cli
   :prog: CLI: geoserver_setup
   :show-nested:


.. _geoserver-yaml-file:

Yaml configuration file
=======================

The cli script must be configured with a ``.yaml`` configuration file.

An example configuration file is located at
:file:`geoimagenet_api/geoserver_setup/config_example.yaml`:

.. literalinclude:: ../../geoimagenet_api/geoserver_setup/config_example.yaml

