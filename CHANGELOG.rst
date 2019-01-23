Changelog
=========

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