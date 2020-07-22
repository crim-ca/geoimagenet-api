*************
Running Tests
*************

The tests consist mostly of integration tests, considering that a large part of the logic needs the
data from postgis to execute.

To setup a postgres database suitable to run the tests, you can use docker-compose::

  docker-compose up -d

This will setup a postgis instance listening on 0.0.0.0:5432.

If you want, you can connect to it with the url::

  postgresql://docker:docker@localhost/gis

You can also run the tests having a local Geoimagenet instance up and running, as long as you change (temporarily) 
variables in geoimagenet_api/config/default.ini, or use a custom.ini file, where:

`postgis_user` and `postgis_password` are equal to the values assigned to them in the env.local of
your instance (the compose repository)
