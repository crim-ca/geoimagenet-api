import re
from itertools import chain
import os

import pytz
from tzlocal import get_localzone
import warnings
from pathlib import Path
from loguru import logger

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


def find_image_trace(images_folder, sensor_name, image_filename_stem: str) -> Path:
    contour_folder = images_folder / f"{sensor_name}_CONTOURS"
    if contour_folder in images_folder.iterdir():
        shapefiles = [f for f in contour_folder.iterdir() if f.suffix.lower() == ".shp"]

        matching_contour = find_matching_name(
            image_filename_stem, [f.stem for f in shapefiles], attrs_filter={"trace": True}
        )
        if matching_contour:
            for contour in shapefiles:
                if contour.stem == matching_contour:
                    return contour


def wkt_multipolygon_to_polygon(wkt: str) -> str:
    """Take the first polygon from a wkt multipolygon and return it as a polygon.

    If there is any hole in this first polygon, return the first ring.
    """
    srid = None
    if wkt.startswith("SRID="):
        srid, wkt = wkt.split(";")

    if wkt.startswith("POLYGON"):
        pass
    elif wkt.startswith("MULTIPOLYGON"):
        geom = re.search(r"\(\(\((.+?)\)", wkt).group(1)
        wkt = f"POLYGON (({geom}))"
    else:
        raise ValueError("Expected a multipolygon or a polygon")

    if srid:
        wkt = ";".join([srid, wkt])

    return wkt
