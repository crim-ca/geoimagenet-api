Changelog
=========


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