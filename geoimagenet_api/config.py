import os
from pathlib import Path
import configparser

config_ini = None
ENVIRONMENT_PREFIX = "GEOIMAGENET_API_"


def get(parameter_name: str):
    """
    Get a configuration parameter.
    The priorities are:
      - environment variables prefixed by `ENVIRONMENT_PREFIX`
      - parameters in the config.ini file
    :param parameter_name: the name of the config element to get
    """
    global config_ini

    if config_ini is None:
        config_ini = configparser.ConfigParser()
        config_filename = Path(__file__).with_name("config.ini")
        config_ini.read(config_filename)

    environment_variable = ENVIRONMENT_PREFIX + parameter_name.upper()
    if environment_variable in os.environ:
        return os.environ[environment_variable]
    else:
        return config_ini["geoimagenet_api"][parameter_name]
