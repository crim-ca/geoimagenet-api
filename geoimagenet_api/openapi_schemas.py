from __future__ import annotations
from typing import List, Union, Any

from pydantic import BaseModel, Schema

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
    # Workaround OpenAPI recursive reference, using Any
    children: List[Any] = Schema([], description="A list of 'TaxonomyClass' objects.")


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


class ExecuteIOValue(BaseModel):
    id: str
    value: Union[str, int, float, bool]


class ExecuteIOHref(BaseModel):
    id: str
    href: str


class BatchPostForwarded(BaseModel):
    inputs: List[Union[ExecuteIOValue, ExecuteIOHref]]
    outputs: List[Union[ExecuteIOValue, ExecuteIOHref]] = []


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


annotation_ids_schema = Schema(
    ...,
    description="Must be an array of string like: "
    "['annotation.1234', 'annotation.1235', ...]. "
    "This is the standard OpenLayers format.",
)


class AnnotationRequestReview(BaseModel):
    annotation_ids: List[str] = annotation_ids_schema
    boolean: bool = Schema(
        ..., description="Boolean whether to turn on or off the review request."
    )


class AnnotationProperties(BaseModel):
    annotator_id: int
    taxonomy_class_id: int
    image_name: str
    status: AnnotationStatus = AnnotationStatus.new


class AnnotationStatusUpdateIds(BaseModel):
    annotation_ids: List[str] = annotation_ids_schema


class AnnotationStatusUpdateTaxonomyClass(BaseModel):
    taxonomy_class_id: int
    with_taxonomy_children: bool = Schema(
        True,
        description="If true, the taxonomy_class_id will also include its children.",
    )


class Point(BaseModel):
    type: str = Schema(..., regex="Point")
    coordinates: List[float]


class LineString(BaseModel):
    type: str = Schema(..., regex="LineString")
    coordinates: List[List[float]]


class Polygon(BaseModel):
    type: str = Schema(..., regex="Polygon")
    coordinates: List[List[List[float]]]


class MultiPolygon(BaseModel):
    type: str = Schema(..., regex="MultiPolygon")
    coordinates: List[List[List[List[float]]]]


AnyGeojsonGeometry = Union[Point, LineString, Polygon, MultiPolygon]


class GeoJsonFeature(BaseModel):
    type: str = Schema(..., regex="Feature")
    geometry: AnyGeojsonGeometry
    properties: AnnotationProperties
    id: str = None


class CRSCode(BaseModel):
    code: int


class CRS(BaseModel):
    type: str = Schema(..., regex="EPSG")
    properties: CRSCode


class GeoJsonFeatureCollection(BaseModel):
    type: str = Schema(..., regex="FeatureCollection")
    crs: CRS
    features: List[GeoJsonFeature] = []
