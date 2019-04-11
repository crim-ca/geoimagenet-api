"""
Command line script to configure geoserver from a configuration file.
"""
import sys
from pathlib import Path

from loguru import logger
import click

from geoimagenet_api.config import config
from geoimagenet_api.geoserver_setup.geoserver_datastore import GeoServerDatastore
from geoimagenet_api.geoserver_setup.geoserver_mirror import GeoServerMirror


def main(
    gs_datastore_url: str,
    gs_datastore_user: str,
    gs_datastore_password: str,
    gs_mirror_url: str,
    gs_mirror_user: str,
    gs_mirror_password: str,
    gs_yaml_config: str,
    dry_run=False,
):
    logger.info(f"## Configuring datastore")
    GeoServerDatastore(
        gs_datastore_url,
        gs_datastore_user,
        gs_datastore_password,
        gs_yaml_config,
        dry_run,
    ).configure()

    logger.info(f"## Configuring GeoServer mirror instance")
    GeoServerMirror(
        gs_datastore_url,
        gs_datastore_user,
        gs_datastore_password,
        gs_mirror_url,
        gs_mirror_user,
        gs_mirror_password,
        gs_yaml_config,
        dry_run,
    ).configure()


@click.command()
@click.option(
    "-d",
    "--dry-run",
    is_flag=True,
    help="Only print actions to perform without changing the remote server.",
)
@click.option("--gs-yaml-config", help="Path to the yaml configuration file")
@click.option(
    "--gs-datastore-url",
    help="GeoServer instance where the GeoTIFF images are served from.",
)
@click.option("--gs-datastore-user", help="Username to connect to Geoserver datastore")
@click.option(
    "--gs-datastore-password",
    prompt=True,
    hidden=True,
    help="Password to connect to Geoserver datastore",
)
@click.option(
    "--gs-mirror-url",
    help="GeoServer instance where the GeoTIFF images are served from.",
)
@click.option(
    "--gs-mirror-user", help="Username to connect to Geoserver mirror service"
)
@click.option(
    "--gs-mirror-password",
    prompt=True,
    hidden=True,
    help="Password to connect to Geoserver mirror service",
)
def cli(
    dry_run,
    gs_yaml_config,
    gs_datastore_url,
    gs_datastore_user,
    gs_datastore_password,
    gs_mirror_url,
    gs_mirror_user,
    gs_mirror_password,
):
    """Main entry point for the cli."""

    def _set(variable, variable_name):
        if not variable:
            variable = config.get(variable_name, str)
        if not variable:
            logger.error(f"'{variable_name}' required, exiting.")
            sys.exit(1)
        return variable

    gs_datastore_url = _set(gs_datastore_url, "gs_datastore_url")
    gs_datastore_user = _set(gs_datastore_user, "gs_datastore_user")
    gs_datastore_password = _set(gs_datastore_password, "gs_datastore_password")
    gs_mirror_url = _set(gs_mirror_url, "gs_mirror_url")
    gs_mirror_user = _set(gs_mirror_user, "gs_mirror_user")
    gs_mirror_password = _set(gs_mirror_password, "gs_mirror_password")

    if not gs_yaml_config:
        gs_yaml_config = Path(__file__).with_name("config.yaml")
        if not gs_yaml_config.exists():
            gs_yaml_config = None
    gs_yaml_config = Path(_set(gs_yaml_config, "gs_yaml_config"))

    logger.debug(f"Started with input file: {gs_yaml_config}")

    main(
        gs_datastore_url,
        gs_datastore_user,
        gs_datastore_password,
        gs_mirror_url,
        gs_mirror_user,
        gs_mirror_password,
        gs_yaml_config,
        dry_run,
    )


if __name__ == "__main__":
    cli(auto_envvar_prefix="GEOIMAGENET_API")
