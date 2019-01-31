from flask import request

from geoimagenet_api.openapi_schemas import ApiInfo
from geoimagenet_api import __version__, __author__, __email__


def get() -> ApiInfo:
    docs_url = request.url + "ui"
    changelog_url = request.url + "changelog"
    return ApiInfo(
        name="GeoImageNet API",
        version=__version__,
        authors=__author__,
        email=__email__,
        documetation_url=docs_url,
        changelog_url=changelog_url,
    )
