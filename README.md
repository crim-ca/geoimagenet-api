# GeoImageNet API

Web platform API


### Configuration

An example configuration file is located at: `geoimagenet_api/config/default.ini`

No other configuration parameters are used, and these are the defaults.

Configuration parameters are loaded in this order of priority:
  - environment variables prefixed by `GEOIMAGENET_API_` (ex: `GEOIMAGENET_API_POSTGIS_DB`)
  - parameters in the ini file located in the `GEOIMAGENET_API_CONFIG` environment variable
  - parameters in the `geoimagenet_api/config/custom.ini file` (should be used mostly for development, this file is ignored by git)
  - parameters in the `geoimagenet_api/config/default.ini file`
  
  
### GeoServer Setup

``` bash
$ geoserver_setup GEOSERVER_URL CONFIG.YAML
```

This commands creates workspaces, stores, layers and styles
described in a yaml file. 

An example configuration file is located at: 
`geoimagenet_api/geoserver_setup/config_example.yaml`

Eventually, this command will be available through the rest api.
Right now, it has to be triggered manually.

  
### Migrations


``` bash
$ migrate upgrade head
```

`migrate` is only an alias for `alembic`. 
The url used by alembic to connect to the database will be the same 
as the one used in the global configuration described above.

### Initialize the database with data

``` bash
$ init_database
```

This command is designed to be idempotent. Unique constraints shouldn't allow duplicate data,
but you should be careful when loading data into the database.
Any required migrations will be applied by this command prior to inserting the data.

To write data for testing purposes, its possible to run:

``` bash
$ init_database --testing
``` 


### Running tests

The tests consist mostly of integration tests, considering that a large part of the logic needs the
data from the database to execute. 

To setup a postgres database suitable to run the tests, you can run the following docker container:

```bash
$ docker run -d --rm --name 'postgis' -e ALLOW_IP_RANGE="0.0.0.0/0" -e IP_LIST='*' \
  -e POSTGRES_DB=gis -e POSTGRES_USER=docker -e POSTGRES_PASS=docker -p 5432:5432 kartoza/postgis:9.6-2.4
```