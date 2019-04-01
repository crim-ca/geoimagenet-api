"""GeoImageNet API to support the web mapping platform"""
import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import PlainTextResponse, RedirectResponse

import sentry_sdk

from geoimagenet_api.__about__ import __version__, __author__, __email__
from geoimagenet_api.database import connection, migrations
from geoimagenet_api import config

from geoimagenet_api import endpoints

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
    sentry_sdk.init(dsn=sentry_dsn)

base_app = FastAPI()
app = FastAPI(
    openapi_prefix="/api/v1",
    title="GeoImageNet Annotations API",
    description="API for the GeoImageNet platform",
    version=__version__
)
base_app.mount("/api/v1", app)

logger.info("App initialized")


@base_app.get("/api/", include_in_schema=False)
def redirect_v1():
    return RedirectResponse(url="/api/v1")


@app.get("/changelog/", include_in_schema=False, content_type=PlainTextResponse)
def changelog():
    return Path(__file__).with_name("CHANGELOG.rst").read_text()


app.include_router(endpoints.router)

if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(base_app, host="0.0.0.0", port=8080)
