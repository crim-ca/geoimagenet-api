from collections import OrderedDict

import dataclasses
from connexion.apps.flask_app import FlaskJSONEncoder

from geoimagenet_api.openapi_schemas import Optional


def dataclass_from_object(data_cls, source_obj, depth=None):
    fields = [f.name for f in dataclasses.fields(data_cls)]
    common_fields = [f for f in dir(source_obj) if f in fields]
    properties = {}
    for field in common_fields:
        value = getattr(source_obj, field)
        if isinstance(value, list) and len(value) and isinstance(value[0], type(source_obj)):
            # recursive data type
            if depth is None or depth > 0:
                new_depth = depth - 1 if depth is not None else None
                value = [dataclass_from_object(data_cls, v, new_depth) for v in value]
            else:
                value = []
        properties[field] = value
    return data_cls(**properties)


class DataclassEncoder(FlaskJSONEncoder):
    def __init__(self, *args, **kwargs):
        super(DataclassEncoder, self).__init__(*args, **kwargs)
        self.sort_keys = False

    def encode(self, obj):
        if isinstance(obj, (tuple, list)):
            obj = [_dataclass_to_dict(o) for o in obj]
        else:
            obj = _dataclass_to_dict(obj)

        return super(DataclassEncoder, self).encode(obj)


def _dataclass_to_dict(obj):
    """Transforms dataclasses to a dict, ignoring Optional fields if they're empty"""

    def dict_factory(result):
        return OrderedDict([r for r in result if not r[1] == Optional])

    if dataclasses.is_dataclass(obj):
        obj = dataclasses.asdict(obj, dict_factory=dict_factory)
    return obj
