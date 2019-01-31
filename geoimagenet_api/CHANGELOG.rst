Changelog
=========

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