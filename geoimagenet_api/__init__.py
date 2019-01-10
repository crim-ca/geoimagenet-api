"""GeoImageNet API to support the web mapping platform"""

import connexion
from flask import redirect, request

from geoimagenet_api.__about__ import __version__, __author__, __email__
from geoimagenet_api.utils import DataclassEncoder
from geoimagenet_api.database import connection, migrations
from geoimagenet_api import config

if config.get("wait_for_db_connection_on_import", bool):
    connection.wait_for_db_connection()

if config.get("sentry_url", str):
    import sentry_sdk

    sentry_sdk.init(config.get("sentry_url", str))


def make_app(validate_responses=False):
    app = connexion.App(__name__, port=8080)
    app.add_api(
        "openapi.yaml",
        strict_validation=True,
        validate_responses=validate_responses,
        resolver=connexion.RestyResolver("geoimagenet_api.routes"),
        resolver_error=404,
    )
    app.app.json_encoder = DataclassEncoder

    @app.app.route("/api/")
    def root():
        return redirect(request.url + "v1/")

    return app


app = make_app()
application = app.app

if __name__ == "__main__":
    app.run()
