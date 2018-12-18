from collections import OrderedDict

import dataclasses
from connexion.apps.flask_app import FlaskJSONEncoder

from geoimagenet_api.openapi_schemas import Optional


def dataclass_from_object(data_cls, source_obj):
    fields = [f.name for f in dataclasses.fields(data_cls)]
    source_items = source_obj.__dict__.items()
    filtered_properties = {k: v for k, v in source_items if k in fields}
    return data_cls(**filtered_properties)


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
