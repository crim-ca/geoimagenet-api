import sys
from pathlib import Path
from typing import List

from dataclasses import dataclass

from loguru import logger
import click
import yaml
from geoserver.catalog import Catalog


@dataclass
class Style:
    name: str
    path: str


@dataclass
class Workspace:
    name: str
    uri: str
    style: str
    images_path: str


class GeoServerConfiguration:
    extensions = {".tif": "GeoTIFF"}

    def __init__(self, geoserver_url, yaml_config, dry_run):
        self.geoserver_url = geoserver_url.rstrip("/")
        if not self.geoserver_url.endswith("/rest"):
            self.geoserver_url += "/rest"

        self.yaml_config = yaml_config
        self.dry_run = dry_run

        self._catalog = None

    def configure(self):
        self.remove_workspaces()

        styles = [Style(**s) for s in self.yaml_config["styles"]]
        workspaces = [Workspace(**s) for s in self.yaml_config["workspaces"]]

        self.create_workspaces(workspaces)
        self.create_styles(styles)
        self.create_stores(workspaces)

    def get_global_config(self, name):
        if "global" not in self.yaml_config:
            logger.error("Missing 'global' section in config")
            sys.exit(1)
        if name not in self.yaml_config["global"]:
            logger.error(f"Missing '{name}' parameter in global section in config")
            sys.exit(1)

        return self.yaml_config["global"][name]

    @property
    def catalog(self):
        if self._catalog is None:
            logger.info(f"Getting catalog from {self.geoserver_url}")
            self._catalog = Catalog(self.geoserver_url)
        return self._catalog

    @property
    def workspaces(self):
        catalog = self.catalog
        logger.info(f"Getting workspaces")
        return catalog.get_workspaces()

    def remove_workspaces(self):
        delete_other_workspaces = self.get_global_config("delete_other_workspaces")
        overwrite_workspaces = self.get_global_config("overwrite_workspaces")

        if delete_other_workspaces or overwrite_workspaces:
            existing_workspaces = self.workspaces
            workspaces_to_create = self.yaml_config.get("workspaces", [])
            workspaces_names_to_create = [w["name"] for w in workspaces_to_create]

            for workspace in existing_workspaces:
                workspace_exists = workspace.name in workspaces_names_to_create
                if (
                    overwrite_workspaces
                    and workspace_exists
                    or delete_other_workspaces
                    and not workspace_exists
                ):
                    logger.warning(f"DELETE workspace: {workspace.href}")
                    if not self.dry_run:
                        self.catalog.delete(workspace, recurse=True)

    def create_workspaces(self, workspaces: List[Workspace]):
        existing_workspaces = self.workspaces
        existing_workspaces_names = [w.name for w in existing_workspaces]

        for w in workspaces:
            if w.name not in existing_workspaces_names:
                logger.warning(f"CREATE workspace: name={w.name}, uri={w.uri}")
                if not self.dry_run:
                    self.catalog.create_workspace(name=w.name, uri=w.uri)

    def create_styles(self, styles: List[Style]):
        for style in styles:
            name, path = style.name, Path(style.path)
            if not path.exists():
                logger.error(f"Path to style {name} doesn't exists: {path}")
                sys.exit(1)

            data = path.read_text()

            logger.warning(f"CREATE style: {name}")
            if not self.dry_run:
                self.catalog.create_style(
                    name,
                    data,
                    overwrite=True,
                    workspace=None,
                    style_format="sld10",
                    raw=False,
                )

    def create_stores(self, workspaces: List[Workspace]):
        existing_styles = {s.name: s for s in self.catalog.get_styles()}

        for workspace in workspaces:
            logger.info(f"Getting stores for workspace {workspace.name}")
            stores = self.catalog.get_stores(workspaces=workspace.name)
            stores_names = [s.name for s in stores]
            images_path = workspace.images_path
            if images_path:
                for path in Path(images_path).glob("./*.*"):
                    image_name = path.stem
                    if image_name in stores_names:
                        logger.warning(f"Store already exists: {image_name}")
                        continue
                    type_ = self.extensions.get(path.suffix.lower())
                    if type_ is not None:
                        logger.warning(f"CREATE {type_} store: {image_name}")
                        if not self.dry_run:
                            layer_name = image_name
                            self.catalog.create_coveragestore(
                                image_name,
                                workspace=workspace.name,
                                path=str(path),
                                type=type_,
                                create_layer=True,
                                layer_name=layer_name,
                                source_name=layer_name,
                            )
                            layer = self.catalog.get_layer(layer_name)
                            layer.default_style = existing_styles[workspace.style]
                            self.catalog.save(layer)


def setup(geoserver_url: str, config: str, dry_run=False):
    logger.info(f"Loading config file.")
    config = yaml.safe_load(open(config))

    geoserver_config = GeoServerConfiguration(geoserver_url, config, dry_run)

    geoserver_config.configure()


@click.command()
@click.option(
    "--dry-run",
    default=False,
    help="Only print actions to perform without changing the remote server.",
)
@click.argument("geoserver_url")
@click.argument("config")
def cli(dry_run, geoserver_url, config):
    """Main entry point for the cli."""
    logger.info(f"Started with input file: {config}")
    if not Path(config).exists():
        logger.error("File doesn't exist, exiting.")
        sys.exit(1)

    setup(geoserver_url, config, dry_run)


if __name__ == "__main__":
    # url = 'https://192.168.99.201/geoserver'
    url = "http://192.168.99.201:8080/geoserver"
    config = "./config_example.yaml"
    setup(url, config)
