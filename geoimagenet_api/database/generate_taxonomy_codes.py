import json

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import TaxonomyClass
from geoimagenet_api.endpoints.taxonomy_classes import get_taxonomy_classes_tree


def make_json_from_database(taxonomy_id):  # pragma no cover
    """For a taxonomy, generate a json file from the database.

    The output format is suitable to be edited manually afterwards.

    This is a helper function used halfway through migration 66711f6c50e1_13_taxonomy_updates.py.
    The point was to generate the codes from the database, and then re-create the json document from it.
    """
    with connection_manager.get_db_session() as session:
        root_id = (
            session.query(TaxonomyClass.id)
            .filter_by(taxonomy_id=taxonomy_id, parent_id=None)
            .scalar()
        )
        tree = get_taxonomy_classes_tree(session=session, taxonomy_class_id=root_id)

        def recurse_tree(branch):
            data = {
                "name": {"fr": branch.name_fr or "", "en": branch.name_en or ""},
                "code": branch.code,
            }
            if branch.children:
                data["value"] = [recurse_tree(c) for c in branch.children]
            return data

        output = {"version": 1}
        output.update(recurse_tree(tree))
        return output


if __name__ == "__main__":  # pragma no cover
    outputs = ["objets.json", "couverture_de_sol.json"]
    for output, taxonomy_id in zip(outputs, [1, 2]):
        data = make_json_from_database(taxonomy_id)
        json.dump(data, open(output, "w"), ensure_ascii=False, indent=4)
