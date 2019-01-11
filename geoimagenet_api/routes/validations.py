import connexion

from geoimagenet_api.openapi_schemas import Validation, ValidationPost
from geoimagenet_api.database.models import ValidationEvent as DBValidation
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import dataclass_from_object


def search(annotation_id=None, validator_id=None):
    filter_by = {k: v for k, v in locals().items() if v is not None}
    with connection_manager.get_db_session() as session:
        validations = session.query(DBValidation).filter_by(**filter_by)
        validations = [dataclass_from_object(Validation, t) for t in validations]
        if not validations:
            return "No validation found", 404
        return validations


def post():
    data = ValidationPost(**connexion.request.get_json())
    with connection_manager.get_db_session() as session:
        validations = []
        for id_ in data.annotation_ids:
            validation = DBValidation(annotation_id=id_, validator_id=data.validator_id)
            validations.append(validation)

        session.add_all(validations)
        session.commit()
        return [dataclass_from_object(Validation, t) for t in validations]
