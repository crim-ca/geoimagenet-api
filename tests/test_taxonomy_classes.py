
import pytest
import pp

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.routes.taxonomy_classes import query_taxonomy_tree, query_taxonomy_classes_with_depth


def test_query_taxonomy_tree():
    from time import perf_counter
    t = perf_counter()
    for _ in range(100):
        with connection_manager.get_db_session() as session:
            taxonomy_id = 1
            r = query_taxonomy_tree(session, taxonomy_id)
    print("%.3f" % (perf_counter() - t, ))
    t = perf_counter()
    for _ in range(100):
        with connection_manager.get_db_session() as session:
            r = query_taxonomy_classes_with_depth(session, filter_by={"id": 1}, depth=10)
    print("%.3f" % (perf_counter() - t, ))
