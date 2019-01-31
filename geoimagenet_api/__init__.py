"""GeoImageNet API to support the web mapping platform"""
import logging
import sys
from pathlib import Path

import connexion
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from flask import redirect, request, render_template, Response

from geoimagenet_api.__about__ import __version__, __author__, __email__
from geoimagenet_api.utils import DataclassEncoder
from geoimagenet_api.database import connection, migrations
from geoimagenet_api import config

logger = logging.getLogger(__name__)

if __name__ == "geoimagenet_api":
    FORMAT = "%(asctime)-15s %(name)-12s %(levelname)-8s %(message)s"
    fmt = logging.Formatter(FORMAT)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

if config.get("wait_for_db_connection_on_import", bool):
    logger.info("Waiting for database connection")
    connection.wait_for_db_connection()

sentry_dsn = config.get("sentry_url", str)
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn, integrations=[FlaskIntegration(transaction_style="url")]
    )


def make_app(validate_responses=False):
    options = {"swagger_ui": False}
    connexion_app = connexion.App(__name__, port=8080, options=options)
    connexion_app.add_api(
        "openapi.yaml",
        strict_validation=True,
        validate_responses=validate_responses,
        resolver=connexion.RestyResolver("geoimagenet_api.routes"),
        resolver_error=404,
    )
    connexion_app.app.json_encoder = DataclassEncoder

    @connexion_app.app.route("/api/")
    def root():
        return redirect(request.url + "v1/")

    @connexion_app.app.route("/api/v1/ui/")
    def redoc():
        return render_template("redoc.html")

    @connexion_app.app.route("/api/v1/changelog/")
    def changelog():
        changes = Path(__file__).with_name("CHANGELOG.rst").read_text()
        return Response(changes, mimetype='text/plain')

    logger.info("App initialized")

    return connexion_app


app = make_app()
application = app.app

if __name__ == "__main__":
    app.run()
