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


@dataclass
class Taxonomy:
    id: int
    name: str
    slug: str
    version: str
    root_taxonomy_class_id: int


@dataclass
class TaxonomyVersion:
    taxonomy_id: int
    root_taxonomy_class_id: int
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
class Batch:
    id: int
    created_by: int
    created_at: datetime


@dataclass
class ValidationPost:
    annotation_ids: List[int]
    validator_id: int


@dataclass
class AnnotationCount:
    new: int = field(default=0)
    pre_released: int = field(default=0)
    released: int = field(default=0)
    review: int = field(default=0)
    validated: int = field(default=0)
    rejected: int = field(default=0)
    deleted: int = field(default=0)

    def __add__(self, other):
        return AnnotationCount(
            new=self.new + other.new,
            pre_released=self.pre_released + other.pre_released,
            released=self.released + other.released,
            review=self.review + other.review,
            validated=self.validated + other.validated,
            rejected=self.rejected + other.rejected,
            deleted=self.deleted + other.deleted,
        )

    def __iadd__(self, other):
        self.new += other.new
        self.pre_released += other.pre_released
        self.released += other.released
        self.review += other.review
        self.validated += other.validated
        self.rejected += other.rejected
        self.deleted += other.deleted
        return self


@dataclass
class AnnotationCounts:
    taxonomy_class_id: int
    counts: AnnotationCount


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
