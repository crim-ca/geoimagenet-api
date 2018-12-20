"""GeoImageNet API to support the web mapping platform"""

from .__about__ import __version__, __author__, __email__

import connexion
from geoimagenet_api.utils import DataclassEncoder

app = connexion.App(__name__, port=8080)
app.add_api(
    "openapi.yaml",
    strict_validation=True,
    validate_responses=False,
    resolver=connexion.RestyResolver("geoimagenet_api.routes"),
    resolver_error=404,
)
app.app.json_encoder = DataclassEncoder
application = app.app
