
**************
 Configuration
**************

.. _configuration:

====================
Global configuration
====================

An example configuration file is located at: :file:`geoimagenet_api/config/default.ini`

No other configuration parameters are used, and these are the defaults.

Configuration parameters are loaded in this order of priority:
  - environment variables prefixed by ``GEOIMAGENET_API_`` (ex: ``GEOIMAGENET_API_POSTGIS_DB``)
  - parameters in the ini file located in the ``GEOIMAGENET_API_CONFIG`` environment variable
  - parameters in the :file:`geoimagenet_api/config/custom.ini` file (should be used mostly for development, this file is ignored by git)
  - parameters in the :file:`geoimagenet_api/config/default.ini` file


=========
GeoServer
=========

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

