import os
from pathlib import Path
import configparser

# global variable used to read configuration files only once
config_ini = None
# prefix to use in environment variables
ENVIRONMENT_PREFIX = "GEOIMAGENET_API_"


def _load_config_ini():
    global config_ini
    if config_ini is None:
        config_ini = configparser.ConfigParser()
        here = Path(__file__).parent
        filenames = [
            here / "default.ini",
            here / "custom.ini",
            _get_environment_var("CONFIG", default=""),
        ]
        config_ini.read(filenames)

    return config_ini


def _get_environment_var(parameter_name, default=None):
    environment_variable = ENVIRONMENT_PREFIX + parameter_name.upper()
    return os.environ.get(environment_variable, default)


def get(parameter_name: str, type_):
    """
    Get a configuration parameter.
    In order of priority:
      - environment variables prefixed by `GEOIMAGENET_API_`
      - parameters in the ini file located in GEOIMAGENET_API_CONFIG environment variable
      - parameters in the ./custom.ini file
      - parameters in the ./default.ini file
    :param parameter_name: the name of the config element to get
    :param type_: the type of the parameter. Booleans are handled. (ex: bool('false') -> False)
    """
    config = _load_config_ini()

    configuration = config["geoimagenet_api"]
    if parameter_name not in configuration:
        raise KeyError("Parameter name not found in configuration.")

    from_environment = _get_environment_var(parameter_name)
    from_config = configuration[parameter_name]

    conversion_function = {
        bool: _convert_bool
    }.get(type_, type_)

    return conversion_function(from_environment or from_config)


def _convert_bool(value):
    boolean_states = configparser.ConfigParser.BOOLEAN_STATES
    if value.lower() not in boolean_states:
        raise ValueError('Not a boolean: %s' % value)
    return boolean_states[value.lower()]


def get_database_url():
    db = get("postgis_db", str)
    username = get("postgis_user", str)
    password = get("postgis_password", str)
    url = f"postgresql://{username}:{password}@192.168.99.201/{db}"

    return url
