import enum
import json
from typing import List

import sqlalchemy.orm
from starlette.requests import Request


def get_logged_user(request: Request) -> int:
    # todo: use the id of the currently logged in user
    return 1


async def geojson_stream(
    query: sqlalchemy.orm.Query, properties: List, with_geometry: bool = True
):
    """Stream the geojson features from the database.

    So that the whole FeatureCollection is not built entirely in memory.
    The bulk of the json serialization (the geometries) takes place in the database
    doing all the serialization in the database is a very small
    performance improvement and I prefer to build the json in python than in sql.
    """

    feature_collection = {"type": "FeatureCollection"}
    if with_geometry:
        feature_collection["crs"] = {"type": "EPSG", "properties": {"code": 3857}}
    feature_collection["features"] = []

    feature_collection = json.dumps(feature_collection)

    before_ending_brackets = feature_collection[:-2]
    ending_brackets = feature_collection[-2:]

    yield before_ending_brackets
    first_result = True
    for r in query:
        if not first_result:
            yield ","
        else:
            first_result = False

        data = {
            "type": "Feature",
            "id": f"annotation.{r.id}",
            "properties": {p: _get_attr(r, p) for p in properties},
        }

        if with_geometry:
            # geometry is already serialized
            data["geometry"] = "__geometry"
            data = json.dumps(data).replace('"__geometry"', r.geometry)
        else:
            data = json.dumps(data)

        yield data

    yield ending_brackets


def _get_attr(object, name):
    value = getattr(object, name)
    if isinstance(value, enum.Enum):
        value = value.value
    return value
