Changelog
=========

0.7.0 (2019-02-05)
------------------

Changes
~~~~~~~
- Change the format of the annotation counts to... [David Caron]

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