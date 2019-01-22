import os
import sys
from pathlib import Path
from typing import List

from dataclasses import dataclass

from loguru import logger
import click
import yaml
from geoserver.catalog import Catalog

from geoimagenet_api.config import config


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

    def __init__(self, geoserver_url, yaml_path, dry_run):
        self.geoserver_url = geoserver_url.rstrip("/")
        if not self.geoserver_url.endswith("/rest"):
            self.geoserver_url += "/rest"

        self.yaml_path = yaml_path
        self.yaml_config = yaml.safe_load(open(self.yaml_path))

        self.dry_run = dry_run

        self._catalog = None

    def configure(self):
        self.remove_workspaces()

        styles = [Style(**s) for s in self.yaml_config["styles"]]
        workspaces = [Workspace(**s) for s in self.yaml_config["workspaces"]]

        logger.debug("Read workspaces: " + ", ".join(w.name for w in workspaces))
        logger.debug("Read styles: " + ", ".join(s.name for s in styles))

        self.create_workspaces(workspaces)
        self.create_styles(styles)
        self.create_stores(workspaces)

    def get_absolute_path(self, path):
        """Paths can be relative to the config.yaml file or absolute"""
        return Path(self.yaml_path).parent / Path(path)

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
        logger.info(f"Removing workspaces")
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
        logger.info(f"Creating workspaces")
        existing_workspaces = self.workspaces
        existing_workspaces_names = [w.name for w in existing_workspaces]

        for w in workspaces:
            if w.name not in existing_workspaces_names:
                logger.warning(f"CREATE workspace: name={w.name}, uri={w.uri}")
                if not self.dry_run:
                    self.catalog.create_workspace(name=w.name, uri=w.uri)

    def create_styles(self, styles: List[Style]):
        logger.info(f"Creating styles")
        for style in styles:
            name, path = style.name, self.get_absolute_path(style.path)
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
        logger.info(f"Creating stores")
        existing_styles = {s.name: s for s in self.catalog.get_styles()}

        for workspace in workspaces:
            logger.info(f"Getting stores for workspace {workspace.name}")
            stores = self.catalog.get_stores(workspaces=workspace.name)
            stores_names = [s.name for s in stores]
            images_path = self.get_absolute_path(workspace.images_path)
            logger.debug(f"images_path: {images_path}")
            if images_path:
                for path in images_path.glob("./*.*"):
                    logger.debug(f"Found image: {path}")
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

    geoserver_config = GeoServerConfiguration(geoserver_url, config, dry_run)

    geoserver_config.configure()


@click.command()
@click.option(
    "-d",
    "--dry-run",
    is_flag=True,
    help="Only print actions to perform without changing the remote server.",
)
@click.option(
    "--geoserver-url",
    help="GeoServer instance where the GeoTIFF images are served from.",
)
@click.option("--yaml-config", help="Path to the yaml configuration file")
def cli(dry_run, geoserver_url, yaml_config):
    """Main entry point for the cli."""

    if not yaml_config:
        yaml_config = config.get("geoserver_yaml_config", str)

    if not yaml_config:
        yaml_config = Path(__file__).with_name('config.yaml')

    yaml_config = Path(yaml_config)

    logger.info(f"Started with input file: {yaml_config}")
    if not yaml_config.exists():
        logger.error(f"File doesn't exist: {yaml_config}.")
        sys.exit(1)

    if not geoserver_url:
        geoserver_url = config.get("geoserver_datastore_url", str)

    setup(geoserver_url, yaml_config, dry_run)
