Changelog
=========

Unreleased
------------------

Changes
~~~~~~~
- Bugfix in how "batches/annotations" route gets Taxonomy ids


1.4.1 (2019-11-12)
------------------

Changes
~~~~~~~
- Bugfix in sql import statement.


1.4.0 (2019-10-18)
------------------

New
~~~
- Add POST on /annotations/datasets for external datasets


1.3.1 (2019-10-09)
------------------

Fix
~~~
- missing routes for GEOIM-280 fix


1.3.0 (2019-10-09)
------------------

New
~~~
- geoserver_setup: Load image traces when present in the CONTOURS folder.
- geoserver_setup: Add image table to geoserver wfs.
- Add trace_simplified column and trigger (updated automatically when trace gets updated).

Fix
~~~
- Fix header Content-Length=4 for 204 No Content return codes.


1.2.2 (2019-09-18)
------------------

Changes
~~~~~~~
- chg: dev: remove unidecode dependency and fix text-unidecode==1.2


1.2.1 (2019-09-12)
------------------

Changes
~~~~~~~
- Changes to taxonomy classes: [David Caron]

  Add:
   - Commercial fen
   - Pedestrian path
   - Bike path

  Rename:
   - Cemetary -> Cemetery


1.2.0 (2019-09-04)
------------------

New
~~~
- Add POST on /annotations/import
  It is now possible to import annotations using a route where no
  verification takes place for the status and the review_requested flag
- Add 'updated_at' property to return value on GET /annotations.
- Add 'last_updated_since' and 'last_updated_before' parameters to
  GET on /annotations

Changes
~~~~~~~
- POST on /annotations is 5x faster
- Don't stream on GET /annotations because twitcher can't handle it
- Add script to documentation to import and export annotations
- Change query from username to annotator_id on GET /annotations
  The username could be different than the one in the magpie database
  and there is no way to know. The single source of truth is the user id
- Add taxonomy_class_code and image_name to GET /annotations


1.1.0 (2019-08-30)
------------------


New
~~~
- Add GET on /users/current/followed_users
- Add POST on /users/current/followed_users
- Add DELETE on /users/current/followed_users/{user_id}


1.0.0 (2019-08-22)
------------------

Changes
~~~~~~~
- Add username parameter to GET /annotations. [David Caron]

Fix
~~~
- Re-trigger annotation name generation for older annotations. [David
  Caron]
- Fix migrations when person email is null. [David Caron]


0.19.0 (2019-08-21)
-------------------

Changes
~~~~~~~
- Add an /images endpoint to query images information
- Set update time correctly when updating an annotation
- keep user information in sync with magpie database
- don't log geometry updates, change some models constraints

Fix
~~~
- Fix bug after fastapi breaking change


0.18.1 (2019-07-04)
-------------------

Changes
~~~~~~~
- Remove 'init-database' cli command and do it automatically
  when the database is new
- Automatically setup geoserver annotation layer. [David Caron]
- Add flag to ignore ssl verification on geoserver mirror. [David Caron]
- Geoserver_setup: by default, don't setup images on the datastore.
  [David Caron]

Fix
~~~
- Require fastapi 0.29.0 as 0.30.0 breaks schema validation for
  nested Union


0.18.0 (2019-06-28)
-------------------

Changes
~~~~~~~
- Add unique 4-letter codes for taxonomy classes and update taxonomy


0.17.1 (2019-06-26)
-------------------

Changes
~~~~~~~
- Add wms layers attributions in geoserver. [David Caron]


0.17.0 (2019-06-17)
-------------------

New
~~~
- The annotator id is taken from magpie, not from the payload

  For:
  - GET on /annotations (using the 'current_user_only' query param)
  - GET on /annotations/counts/{} (using the 'current_user_only' query param)
  - POST on /annotations
  - PUT on /annotations (can't do anything if you don't own the annotation)
  - POST on /annotations/{status_update} (to check rules for allowed status updates)
  - POST on /annotations/request_review (must own the annotation)


0.16.0 (2019-06-12)
-------------------


New
~~~
- Allow querying all the taxonomy classes for a specific taxonomy ...
  [David Caron]

  version or the latest version by default

Fixes
~~~~~
- Require fastapi>=0.29.0 (recent api change) [David Caron]
- Explicitly define Union types as Body parameters ... [David Caron]

  after fastapi 0.27.0 refactored its parsing of parameters
- Add sentry server name and environment configuration. [David Caron]


0.15.9 (2019-05-08)
-------------------


Changes
~~~~~~~
- Change the POST /batches endpoint. [David Caron]

  batch name is generated, not provided by the caller

Fix
~~~
- in geoserver_setup, log a warning instead of crashing if the  ...

folder name does not match the pattern for folders that are not
intended to store satellite images
- fix after fastapi api change


0.15.1 (2019-04-18)
-------------------

Changes
~~~~~~~
- Accept image_name and image_id for POST and PUT on /annotations.
  [David Caron]
- Fix batch creation url endpoint. [David Caron]


0.15.0 (2019-04-16)
-------------------

New
~~~
- When images are loaded in geoserver using the provided command,
  the 16 bits filename of the images is returned in GET /batches/annotations

Changes
~~~~~~~
- Change the response of POST on /batches to include the response ...
  from the batch-creation service
- Batch creation is always done using the latest taxonomy version.
- Change GET /batches to GET /batches/annotations (the url is only used
  when there is a POST to /batches, and won't affect the frontend)
- Add --concurrent-seeds option when seeding GWC. [David Caron]


0.14.1 (2019-04-09)
-------------------

Changes
~~~~~~~
- add IF EXISTS when we drop indices in migration scripts


0.14.0 (2019-04-02)
-------------------

New
~~~
- Add review_requested boolean filter to /annotations/counts/ [David
  Caron]
- Add with_taxonomy_children boolean to /annotations/counts/ [David
  Caron]
- Add GET /annotations to get a geojson with parameters. [David Caron]


0.13.0 (2019-03-29)
-------------------

New
~~~
- Add a 'name' property to annotations of the type
  CODE_+042.000000_-073.000000 (CODE_latitude_longitude)
- Add current_user_only query parameter to annotation counts


0.12.0 (2019-03-29)
-------------------

Changes
~~~~~~~
- Change structure and route of annotation counts grouped by image.
  [David Caron]

  /annotations/counts/{taxonomy_class_id}?group_by_image=true


0.11.0 (2019-03-29)
-------------------

New
~~~
- Add route /annotations/counts_by_image/{taxonomy_class_id} [David
  Caron]

  to get annotation counts grouped by image and status

Changes
~~~~~~~
- Breaking change: french and english in Taxonomy and TaxonomyClasses...
  [David Caron]

  Returned results are in french and english using keys "name_fr" and "name_en". The old "name" is removed.

Other
~~~~~
- Fix taxonomy tree building. [David Caron]


0.10.0 (2019-03-20)
-------------------

New
~~~
- Add POST route /annotations/request_review. [David Caron]

Changes
~~~~~~~
- Remove print statements and document. [David Caron]
- Fix the schema of the Execute body for the batch creation process.
  [David Caron]
- Add 404 on /batches GET and POST. [David Caron]


0.9.0 (2019-02-21)
------------------

New
~~~

- Add POST on /batches and forward to batch creation process. [David Caron]
- Add GET on /batches/{taxonomy_id} to get validated annotations in geojson [David Caron]
- Add CORS. [David Caron]

Changes
~~~~~~~
- Remove batches models. [David Caron]
- Add a ValidationEvent entry for every validated annotations. [David
  Caron]
- Remove unused annotation validation route. [David Caron]
- Clarify annotation_ids type in openapi schema. [David Caron]


0.8.0 (2019-02-08)
------------------

New
~~~
- Annotations: add POST routes to release/validate/reject/delete. [David
  Caron]

Changes
~~~~~~~
- PUT on /annotations only changes 'geometry', 'taxonomy_class_id'...
  [David Caron]

  and 'image_name'
- Fix bug and more tests for GET /users. [David Caron]
- Delete POST on /users. [David Caron]
- Rename /annotations/{taxonomy_class_id}/counts to ... [David Caron]

  /annotations/counts/{taxonomy_class_id} to remove confusion between
  taxonomy_class_id and annotation_id
- Remove DELETE on /annotations. [David Caron]


0.7.0 (2019-02-05)
------------------

Changes
~~~~~~~
- Change the format of the annotation counts to... [David Caron]

example::

  {
    1: {'new': 10, ...}
    2: {'new': 20, ...}
  }


0.6.0 (2019-02-05)
------------------

New
~~~
- Batches can be created from the api. [David Caron]
- Annotation counts at /annotations/{taxonomy_class_id}/counts

    The children of taxonomy_class_id are also returned
    The annotations are grouped by status (new, pre_released, etc.)

Changes
~~~~~~~
- Rename taxonomy_class_root_id -> root_taxonomy_class_id. [David Caron]
- Support other CRS in PUT and POST of /annotations. [David Caron]
- Add taxonomy_class_root_id in GET /taxonomy/{name_slug}/{version}
  [David Caron]
- Return taxonomy_class_root_id in GET /taxonomy. [David Caron]
- Add test using sluggified name of the taxonomy. [David Caron]
- Get a taxonomy class using the full name or sluggified name of the
  taxonomy. [David Caron]
- Add link to changelog. [David Caron]


0.5.0 (2019-01-31)
------------------

New
~~~
- DELETE on /annotations. [David Caron]

Changes
~~~~~~~
- Add route: /annotations/release to release a taxonomy class and...
  [David Caron]

  its children for the current user (todo: get user id from token)
- Migrations: [David Caron]

  - add indices
  - change annotation log description to enum
  - add annotation status enum
  - modify logging triggers accordingly
- Get on /taxonomy_classes returns the number of annotations for each
  class. [David Caron]
- PUSH and PUT on /annotations can take a FeatureCollection or a single
  Feature. [David Caron]

- Api ui is rendered using ReDoc (handles oneOf, etc.)
- Cleanup of GeoJson description in openapi
- Reduce docker image size by 50%: 150Mb. [David Caron]
- Don't raise an error when there are additionalProperties
  in GeoJson objects. [David Caron]


0.4.0 (2019-01-23)
------------------

New
~~~
- POST on /annotations accepts geojson. [David Caron]
- Routes for PUT and POST on annotations. [David Caron]
- GeoServer configuration: Create layer group along with workspace.
  [David Caron]
- Possibility to configure GeoServer from yaml file and command line.
  [David Caron]
- Add users corresponding to each role for testing frontend. [David
  Caron]
- Remove POST on /taxonomy. [David Caron]
- Remove POST on /taxonomy_classes. [David Caron]


0.3.0 (2019-01-21)
------------------

Changes
~~~~~~~
- Change taxonomy endpoint to regroup versions. [David Caron]
- Change default projection form WGS84 lat-lng to 3857. [David Caron]


0.2.5 (2019-01-11)
------------------

New
~~~
- Redirect /api/ to /api/v1/ [David Caron]
- Add link to documentation on main page. [David Caron]

Changes
~~~~~~~
- 10x faster taxonomy_classes queries using eager loading. [David Caron]
- Faster and thread-safe database connections. [David Caron]

  (engine created once, and use sqlalchemy.orm.scoped_session)