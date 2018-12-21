# GeoImageNet API

Web platform API


### Configuration

An example configuration file if located at: `geoimagenet_api/config/default.ini`

No other configuration parameters are used, and these are the defaults.

Configuration parameters are loaded in this order of priority:
  - environment variables prefixed by `GEOIMAGENET_API_` (ex: `GEOIMAGENET_API_POSTGIS_DB`)
  - parameters in the ini file located in the `GEOIMAGENET_API_CONFIG` environment variable
  - parameters in the `geoimagenet_api/config/custom.ini file` (should be used mostly for development, this file is ignored by git)
  - parameters in the `geoimagenet_api/config/default.ini file`