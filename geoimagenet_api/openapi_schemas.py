from __future__ import annotations
from typing import List

from pydantic import BaseModel

from geoimagenet_api.database.models import AnnotationStatus


class ApiInfo(BaseModel):
    name: str
    version: str
    authors: str
    email: str
    documetation_url: str
    changelog_url: str


class User(BaseModel):
    id: int
    username: str
    name: str


class TaxonomyClass(BaseModel):
    id: int
    name_fr: str
    name_en: str
    taxonomy_id: int
    children: List[TaxonomyClass] = []


TaxonomyClass.update_forward_refs()


class Taxonomy(BaseModel):
    id: int
    name_fr: str
    name_en: str
    slug: str
    version: str
    root_taxonomy_class_id: int


class TaxonomyVersion(BaseModel):
    taxonomy_id: int
    root_taxonomy_class_id: int
    version: str


class TaxonomyGroup(BaseModel):
    name_fr: str
    name_en: str
    slug: str
    versions: List[TaxonomyVersion]


class BatchPost(BaseModel):
    name: str
    taxonomy_id: int
    overwrite: bool = False


class AnnotationCountByStatus(BaseModel):
    new: int = 0
    pre_released: int = 0
    released: int = 0
    review: int = 0
    validated: int = 0
    rejected: int = 0
    deleted: int = 0

    def __add__(self, other):
        return AnnotationCountByStatus(
            new=self.new + other.new,
            pre_released=self.pre_released + other.pre_released,
            released=self.released + other.released,
            review=self.review + other.review,
            validated=self.validated + other.validated,
            rejected=self.rejected + other.rejected,
            deleted=self.deleted + other.deleted,
        )


class AnnotationProperties(BaseModel):
    annotator_id: int
    taxonomy_class_id: int
    image_name: str
    status: AnnotationStatus = AnnotationStatus.new


class AnnotationStatusUpdate(BaseModel):
    annotation_ids: List[str] = None
    taxonomy_class_id: int = None
    with_taxonomy_children: bool = True


# class GeoJsonGeometry(BaseModel):
#     type: str
#     coordinates: List


class GeoJsonFeature(BaseModel):
    type: str
    # geometry: GeoJsonGeometry
    properties: AnnotationProperties
    id: str = None


class GeoJsonFeatureCollection(BaseModel):
    features: List[GeoJsonFeature]
    type: str = "FeatureCollection"


class MultiPolygon(BaseModel):
    coordinates: List[List[List[List[float]]]]
    type: str = "MultiPolygon"
