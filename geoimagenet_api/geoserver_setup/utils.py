from itertools import chain
import os
import pytz
from tzlocal import get_localzone
import warnings

with warnings.catch_warnings():
    # ignore importing the ABCs from 'collections' instead of from 'collections.abc'
    warnings.simplefilter("ignore")
    import dateparser


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
