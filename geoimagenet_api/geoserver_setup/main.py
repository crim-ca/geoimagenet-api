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
    seed_cache_only=False,
    concurrent_seeds=None,
    dry_run=False,
):
    logger.info(f"## Configuring datastore")

    datastore = GeoServerDatastore(
        gs_datastore_url,
        gs_datastore_user,
        gs_datastore_password,
        gs_yaml_config,
        dry_run,
    )

    if seed_cache_only:
        datastore.seed_cache(concurrent_seeds)
    else:
        datastore.configure()

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
    help="Only log actions to perform without changing anything on the remote servers.",
)
@click.option(
    "--gs-yaml-config",
    help="Path to the yaml configuration file. Defaults to :file:`geoimagenet_api/geoserver_setup/config.yaml`",
)
@click.option(
    "--gs-datastore-url",
    help="Url to the GeoServer datastore instance where the GeoTIFF images are served from.",
)
@click.option("--gs-datastore-user", help="Username to connect to Geoserver datastore")
@click.option(
    "--gs-datastore-password", help="Password to connect to Geoserver datastore."
)
@click.option(
    "--gs-mirror-url",
    help="Url to the GeoServer instance where the cascading WMS service is located.",
)
@click.option(
    "--gs-mirror-user", help="Username to connect to Geoserver mirror service."
)
@click.option(
    "--gs-mirror-password", help="Password to connect to Geoserver mirror service."
)
@click.option(
    "--seed-cache-only",
    is_flag=True,
    default=False,
    help="If the servers are already configured, only launch the tile caching on the datastore.",
)
@click.option(
    "--concurrent-seeds",
    type=int,
    default=4,
    help="The number of threads to use on GWC when seeding.",
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
    seed_cache_only,
    concurrent_seeds,
):
    """The command line interface to configure the geoserver datastore and a cascading WMS geoserver
    using the REST api of GeoServer.

    The parameters can be given provided in multiple ways, in order of priority :

        - directly to the command line
        - as an environment variable, all caps, with underscores, prefixed by ``GEOIMAGENET_API_``
          (example: ``GEOIMAGENET_API_GS_MIRROR_URL``)
        - in the standard configuration file of geoimagenet_api (see: :ref:`configuration`)

    See :ref:`geoserver-yaml-file` for information about the ``gs-yaml-config`` parameter.

    """

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
        seed_cache_only,
        concurrent_seeds,
        dry_run,
    )


if __name__ == "__main__":
    cli(auto_envvar_prefix="GEOIMAGENET_API")
