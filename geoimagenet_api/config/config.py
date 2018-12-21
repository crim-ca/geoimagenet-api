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


def get(parameter_name: str):
    """
    Get a configuration parameter.
    The priorities are:
      - environment variables prefixed by `ENVIRONMENT_PREFIX`
      - parameters in the ini file located in GEOIMAGENET_API_CONFIG environment variable
      - parameters in the ./custom.ini file
      - parameters in the ./default.ini file
    :param parameter_name: the name of the config element to get
    """
    config = _load_config_ini()

    configuration = config["geoimagenet_api"]
    if parameter_name not in configuration:
        raise KeyError("Parameter name not found in configuration.")

    from_environment = _get_environment_var(parameter_name)
    from_config = configuration[parameter_name]

    return from_environment or from_config
