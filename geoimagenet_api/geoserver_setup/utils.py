from itertools import chain
import os
from typing import List

import pytz
from tzlocal import get_localzone
import warnings
from pathlib import Path
from loguru import logger

import fiona
from shapely.geometry import shape, Polygon

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
) -> str:
    """Finds from the config and loads as a WKT the image trace"""
    image_trace = _find_image_trace(images_folder, sensor_name, image_filename_stem)
    if not image_trace:
        logger.warning(f"Could not find trace for image: {image_filename_stem}")

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


def _find_image_trace(images_folder, sensor_name, image_filename_stem: str) -> Path:
    contour_folder = images_folder / f"{sensor_name}_CONTOURS"
    if contour_folder in images_folder.iterdir():
        contour_filenames = [f.name for f in contour_folder.iterdir()]
        matching_contour = _match_trace_filename(contour_filenames, image_filename_stem)
        if matching_contour:
            return contour_folder / matching_contour


def _match_trace_filename(
    contour_filenames: List[str], image_filename_stem: str
) -> str:
    def make_trace_name_variations(name):
        from itertools import combinations

        possible_replacements = [
            # replace from trace filename to image filename
            ("rgbn", "rgb"),
            ("rgbn", "nrg"),
            ("16bits", "8bits"),
            ("_trace", ""),
        ]
        yield name
        for n in range(1, len(possible_replacements) + 1):
            for replacements in combinations(possible_replacements, n):
                replaced_name = name
                for repl in replacements:
                    replaced_name = replaced_name.replace(repl[0], repl[1])
                yield replaced_name

    image_filename_stem = image_filename_stem.lower()

    for filename in contour_filenames:
        lower_filename = filename.lower()
        name, extension = lower_filename.rsplit(".", 1)
        if extension not in allowed_image_trace_extensions:
            continue
        for variation in make_trace_name_variations(name):
            if image_filename_stem == variation:
                return filename
