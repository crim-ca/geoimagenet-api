from collections import OrderedDict

import dataclasses
from connexion.apps.flask_app import FlaskJSONEncoder


def dataclass_from_object(data_cls, source_obj, depth=0):
    fields = [f.name for f in dataclasses.fields(data_cls)]
    common_fields = [f for f in dir(source_obj) if f in fields]
    properties = {}
    for field in common_fields:
        value = getattr(source_obj, field)
        if (
            isinstance(value, list)
            and len(value)
            and isinstance(value[0], type(source_obj))
        ):
            # recursive data type
            if depth > 0:
                value = [dataclass_from_object(data_cls, v, depth - 1) for v in value]
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
    """Transforms dataclasses to a dict"""
    if dataclasses.is_dataclass(obj):
        obj = dataclasses.asdict(obj, dict_factory=OrderedDict)
    return obj


def get_logged_user(request):
    # todo: use the id of the currently logged in user
    return 1
