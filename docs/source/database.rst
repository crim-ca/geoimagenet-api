
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


Initialization
==============

You can initialize the database with the required data it needs to run
properly (taxonomies, etc.) using the command::

  init_database

This command is designed to be idempotent (running it any number of times will not break anything)
. Unique constraints will not allow duplicate data,
but you should always be careful when loading data into the database.

Any required migrations will be applied by this command prior to inserting the data.

To write more data used for development purposes, its possible to run::

 init_database --testing