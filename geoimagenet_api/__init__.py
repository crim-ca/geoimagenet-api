"""GeoImageNet API to support the web mapping platform"""
import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import PlainTextResponse, RedirectResponse
from starlette.middleware.cors import CORSMiddleware
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

if config.get("wait_for_db_connection_on_import", bool):  # pragma: no cover
    connection.wait_for_db_connection()

sentry_dsn = config.get("sentry_url", str)
if sentry_dsn:
    kwargs = {}
    if config.get("sentry_environment", str):
        kwargs["environment"] = config.get("sentry_environment", str)
    if config.get("sentry_server_name", str):
        kwargs["server_name"] = config.get("sentry_server_name", str)

    sentry_sdk.init(dsn=sentry_dsn, **kwargs)

    with sentry_sdk.configure_scope() as scope:
        scope.set_extra("config", dict(config.get_all_config()))


application = FastAPI()

if config.get("allow_cors", bool):  # pragma: no cover
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

app = FastAPI(
    openapi_prefix="/api/v1",
    title="GeoImageNet Annotations API",
    description="API for the GeoImageNet platform",
    version=__version__,
)
application.mount("/api/v1", app)

logger.info("App initialized")


@application.get("/api/", include_in_schema=False)
def redirect_v1():
    return RedirectResponse(url="/api/v1")


@app.get("/changelog/", include_in_schema=False, response_class=PlainTextResponse)
def changelog():
    return Path(__file__).with_name("CHANGELOG.rst").read_text()


app.include_router(endpoints.router)

if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(application, host="0.0.0.0", port=8080)
