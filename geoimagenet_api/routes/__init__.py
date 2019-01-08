from geoimagenet_api.openapi_schemas import ApiInfo
from geoimagenet_api import __version__, __author__, __email__


def get() -> ApiInfo:
    return ApiInfo(name="Geoimagenet API",
                   version=__version__,
                   authors=__author__,
                   email=__email__)
