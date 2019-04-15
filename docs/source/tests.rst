*************
Running Tests
*************

The tests consist mostly of integration tests, considering that a large part of the logic needs the
data from postgis to execute.

To setup a postgres database suitable to run the tests, you can run the following docker container::

  docker run -d --rm --name 'postgis' \
  -e ALLOW_IP_RANGE="0.0.0.0/0" \
  -e IP_LIST='*' \
  -e POSTGRES_DB=gis \
  -e POSTGRES_USER=docker \
  -e POSTGRES_PASS=docker \
  -p 5432:5432 \
  kartoza/postgis:9.6-2.4

This will setup a postgis instance listening on 0.0.0.0:5432.

If you want, you can connect to it with the url::

  postgresql://docker:docker@localhost/gis
