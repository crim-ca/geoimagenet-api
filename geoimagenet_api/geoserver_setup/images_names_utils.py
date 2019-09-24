"""
This module contains some utility functions that deal with very similar image names.

For example, here are some image names that all refer to some variation
of the same image source:

8 bits RGB:         Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB
8 bits NRG:         Pleiades_20130630_NRG_50cm_8bits_AOI_16_Lethbridge_AB
8 bits RGBN:        Pleiades_20130630_RGBN_50cm_8bits_AOI_16_Lethbridge_AB
16 bits RGBN:       Pleiades_20130630_RGBN_50cm_16bits_AOI_16_Lethbridge_AB
8 bits RGBN trace:  Pleiades_20130630_RGBN_50cm_8bits_AOI_16_Lethbridge_AB_trace
8 bits RGBN bbox:   Pleiades_20130630_RGBN_50cm_8bits_AOI_16_Lethbridge_AB_bbox

Note: ALL functions are meant to be case insensitive, and return capital letters.
"""

import re
import dataclasses
from typing import Dict

re_pleiades = re.compile(
    r"""
    ^(?P<sensor>Pleiades)_     # the sensor name
    (?P<date>\d{8})            # the date the image was taken
    (?P<identifier>\w)?_       # unique identifier in case 2 images are taken on the same date
    (?P<bands>[RGBN]{3,4})_    # the bands in the image
    50cm_
    (?P<bits>\d{1,2})bits_     # bit depth
    AOI_\d{1,3}_
    (?P<city>\w+?)_            # the city the image was taken in
    (?P<province>[A-Z]{2,3})   # the province the image was taken in
    _?(?P<trace>trace)?        # whether the name represents a trace
    _?(?P<bbox>bbox)?          # whether the name represents a bbox
""",
    re.VERBOSE | re.IGNORECASE,
)


@dataclasses.dataclass
class ImageMatch:
    sensor: str
    date: str
    bands: str
    bits: str
    city: str
    province: str
    identifier: str = None
    trace: bool = False
    bbox: bool = False


def pleiades_match(name) -> ImageMatch:
    attrs = {}
    m = re_pleiades.match(name)
    for field in dataclasses.fields(ImageMatch):
        value = m.group(field.name)
        if value is not None:
            value = field.type(value)
            if field.type is str:
                value = value.upper()

        attrs[field.name] = value
    return ImageMatch(**attrs)


def compare_name(name1, name2):
    """Checks if 2 images are related"""
    m1 = pleiades_match(name1)
    m2 = pleiades_match(name2)
    return _is_name_variation(m1, m2)


def _is_name_variation(match1: ImageMatch, match2: ImageMatch):
    return (
        match1.date == match2.date
        and match1.city == match2.city
        and match1.identifier == match2.identifier
        and match1.province == match2.province
    )


def find_matching_name(image_name, names_list, attrs_filter: Dict = None):
    """Finds an image in the same group, ignoring bands, bits, trace and bbox attributes"""
    if attrs_filter is None:
        attrs_filter = {}

    image_name_match = pleiades_match(image_name)
    for name in names_list:
        match2 = pleiades_match(name)
        if not all(getattr(match2, k) == v for k, v in attrs_filter.items()):
            continue
        if _is_name_variation(image_name_match, match2):
            return name
