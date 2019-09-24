from itertools import chain
import os
from typing import Optional

import pytz
from tzlocal import get_localzone
import warnings
from pathlib import Path
from loguru import logger
from epsg_ident import EpsgIdent

import shapefile
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
    """Finds from the config and loads as a WKT the image trace

    Reprojects to EPSG:3857 if necessary.
    """
    image_trace = find_image_trace(images_folder, sensor_name, image_filename_stem)
    if not image_trace:
        logger.warning(f"Could not find trace for image: {image_filename_stem}")
        return

    extension = image_trace.suffix[1:].lower()
    ewkt = None
    if extension == "shp":
        ewkt = _load_shapefile_ewkt(str(image_trace))
    else:
        logger.warning(f"Can't load '.{extension}' images traces yet.")

    if ewkt is not None:
        ewkt = reproject_ewkt(ewkt)

    return ewkt


def reproject_ewkt(ewkt, to_epsg=3857):
    """Transforms a ewkt string with sqlalchemy and postgis functions"""
    from sqlalchemy import func

    if not ewkt.startswith("SRID="):
        raise ValueError("ewkt should start with 'SRID='")

    source_epsg = ewkt[len('SRID='):ewkt.find(";")]

    if source_epsg == str(to_epsg):
        return ewkt
    return func.ST_AsEWKT(func.ST_Transform(func.ST_GeomFromEWKT(ewkt), to_epsg))


def _load_shapefile_ewkt(path: str) -> str:
    prj = Path(path).with_suffix(".prj")
    if not prj.exists():
        raise ValueError("No projection file found for shapefile")
    ident = EpsgIdent()
    ident.read_prj_from_file(str(prj))
    epsg = ident.get_epsg()

    with shapefile.Reader(path) as shp:
        first_geom = shp.shape(0)
        wkt = Polygon(shape(first_geom).exterior.coords).wkt

    ewkt = f"SRID={epsg};" + wkt
    return ewkt


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
