from typing import List
from datetime import datetime

from dataclasses import dataclass, field

from geoimagenet_api.database.models import AnnotationStatus


@dataclass
class ApiInfo:
    name: str
    version: str
    authors: str
    email: str
    documetation_url: str
    changelog_url: str


@dataclass
class User:
    id: int
    username: str
    name: str


@dataclass
class TaxonomyClass:
    id: int
    name: str
    taxonomy_id: int
    children: List["TaxonomyClass"] = field(default_factory=list)
    annotation_count: int = field(default=0)


@dataclass
class Taxonomy:
    id: int
    name: str
    slug: str
    version: str


@dataclass
class TaxonomyVersion:
    taxonomy_id: int
    version: str


@dataclass
class TaxonomyGroup:
    name: str
    slug: str
    versions: List[TaxonomyVersion]


@dataclass
class Validation:
    id: int
    annotation_id: int
    validator_id: int
    created_ad: datetime


@dataclass
class ValidationPost:
    annotation_ids: List[int]
    validator_id: int


@dataclass
class AnnotationProperties:
    annotator_id: int
    taxonomy_class_id: int
    image_name: str
    status: str = field(default=AnnotationStatus.new.name)


@dataclass
class GeoJsonGeometry:
    type: str
    coordinates: List


@dataclass
class GeoJsonFeature:
    type: str
    geometry: GeoJsonGeometry
    properties: AnnotationProperties
    id: str = field(default=None)
