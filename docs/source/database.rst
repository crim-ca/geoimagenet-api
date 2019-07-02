
********
Database
********

The database backend is `Postgis <https://postgis.net/>`_, which is an extension
on top of `PostgreSQL <https://www.postgresql.org/>`_.

Migrations
==========

Once `geoimagenet_api` is installed in your environment, and the database connection
is configured (see :ref:`configuration`), you can migrate the database using
the following command::

  migrate upgrade head

``migrate`` is only an alias for ``alembic``. For more information, use ``migrate --help``
or ``alembic --help``.

The database will be initialized with data if it hadn't been done before (no alembic information).
