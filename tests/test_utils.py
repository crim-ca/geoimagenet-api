from geoimagenet_api.database.models import TaxonomyClass as DBTaxonomyClass
from geoimagenet_api.openapi_schemas import TaxonomyClass
from geoimagenet_api.utils import dataclass_from_object


def test_dataclass_from_object(client):
    taxo = DBTaxonomyClass(taxonomy_id=1, name_fr="test")
    taxo2 = DBTaxonomyClass(taxonomy_id=1, name_fr="test2")
    taxo3 = DBTaxonomyClass(taxonomy_id=1, name_fr="test3", children=[taxo, taxo2])

    taxo_dataclass = dataclass_from_object(TaxonomyClass, taxo3)
    assert len(taxo_dataclass.children) == 0

    taxo_dataclass = dataclass_from_object(TaxonomyClass, taxo3, depth=1)
    assert taxo_dataclass.children[0].name_fr == "test"