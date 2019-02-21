from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import and_

from geoimagenet_api.routes.taxonomy_classes import get_all_taxonomy_classes_ids
from geoimagenet_api.database.models import Annotation as DBAnnotation
from geoimagenet_api.database.connection import connection_manager

