from itertools import chain
import os
from typing import List, Optional

import pytz
from tzlocal import get_localzone
import warnings
from pathlib import Path
from loguru import logger

import fiona
from shapely.geometry import shape, Polygon

from geoimagenet_api.geoserver_setup.images_names_utils import find_matching_name

with warnings.catch_warnings():
    # ignore importing the ABCs from 'collections' instead of from 'collections.abc'
    warnings.simplefilter("ignore")
    import dateparser

allowed_image_trace_extensions = ["json", "shp"]


def find_date(string: str):
    """Find anything that looks like a date inside a filename, using the dateparser module."""

    # dateparser uses pytz, which tries to extract the timezone from the os
    # in some cases (Docker with alpine) the timezone seems to not be set correctly
    # and dateparser raises an error. Setting the environment variable 'TZ' fixes it.
    try:
        get_localzone()
    except pytz.UnknownTimeZoneError:
        os.environ["TZ"] = "America/Montreal"

    separators = " _-"
    splits = chain(*[string.split(c) for c in separators])
    for part in splits:
        date = dateparser.parse(part, locales=["fr-CA", "en-CA"])
        if date:
            return date.strftime("%Y%m%d")


def load_image_trace_geometry(
    images_folder: Path, sensor_name: str, image_filename_stem: str
) -> Optional[str]:
    """Finds from the config and loads as a WKT the image trace"""
    image_trace = find_image_trace(images_folder, sensor_name, image_filename_stem)
    if not image_trace:
        logger.warning(f"Could not find trace for image: {image_filename_stem}")
        return

    extension = image_trace.suffix[1:].lower()
    wkt = None
    if extension == "shp":
        wkt = _load_shapefile(str(image_trace))
    else:
        logger.warning(f"Can't load '.{extension}' images traces yet.")

    return wkt


def _load_shapefile(path) -> str:
    with fiona.open(path) as shp:
        first_geom = next(iter(shp))
        s = shape(first_geom["geometry"])
        polygon = Polygon(s.exterior.coords)
        return polygon.wkt


def find_image_trace(images_folder, sensor_name, image_filename_stem: str) -> Path:
    contour_folder = images_folder / f"{sensor_name}_CONTOURS"
    if contour_folder in images_folder.iterdir():
        shapefiles = [f for f in contour_folder.iterdir() if f.suffix.lower() == ".shp"]

        matching_contour = find_matching_name(
            image_filename_stem, [f.stem for f in shapefiles]
        )
        if matching_contour:
            for contour in shapefiles:
                if contour.stem == matching_contour:
                    return contour
