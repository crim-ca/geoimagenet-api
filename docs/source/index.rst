.. GeoImageNet Annotation API documentation master file, created by
   sphinx-quickstart on Fri Apr 12 15:50:28 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

**************
Annotation API
**************

The GeoImageNet Annotation REST API is the backend for the platform.

Its responsabilities are:

 - Managing the postgis database containing the annotations,
   the taxonomies and a reference to the images
 - Setting up GeoServer datastore and cascading WMS by parsing a directory tree containing
   the images (see :ref:`geoserver-configuration`)
 - Creating batches by forwarding the task to the geoimagenet_ml REST API

==================
Deployed instances
==================

The deployed instances of the API are located at:

Production
----------

 - Main endpoint: https://geoimagenet.crim.ca/api/v1/
 - Swagger Documentation: https://geoimagenet.crim.ca/api/v1/docs
 - Redoc Documentation: https://geoimagenet.crim.ca/api/v1/redoc

Development
-----------

 - Main endpoint: https://geoimagenetdev.crim.ca/api/v1/
 - Swagger Documentation: https://geoimagenetdev.crim.ca/api/v1/docs
 - Redoc Documentation: https://geoimagenetdev.crim.ca/api/v1/redoc


===========
Source code
===========

The source is on stash at: https://www.crim.ca/stash/projects/GEO/repos/geoimagenet_api

========
Contents
========

.. toctree::
   :maxdepth: 3

   installation
   usage
   database
   tests
   configuration
   geoserver
   changelog
