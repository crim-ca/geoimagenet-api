
import pytest
import pp

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.openapi_schemas import TaxonomyClass
from geoimagenet_api.routes.taxonomy_classes import get_taxonomy_tree, query_taxonomy_classes_with_depth, \
    insert_annotation_count
from geoimagenet_api.utils import dataclass_from_object


def test_query_taxonomy_tree():
    from time import perf_counter
    t = perf_counter()
    for _ in range(100):
        with connection_manager.get_db_session() as session:
            taxonomy_id = 1
            taxo_root = get_taxonomy_tree(session, taxonomy_id, taxonomy_class_id=2)
            # taxo = [dataclass_from_object(TaxonomyClass, t, depth=10) for t in taxo_root]
            # insert_annotation_count(session, taxo)
    print("%.3f" % (perf_counter() - t, ))
    # t = perf_counter()
    # for _ in range(100):
    #     with connection_manager.get_db_session() as session:
    #         r = query_taxonomy_classes_with_depth(session, filter_by={"id": 1}, depth=10)
    # print("%.3f" % (perf_counter() - t, ))
