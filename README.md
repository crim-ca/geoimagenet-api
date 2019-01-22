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
