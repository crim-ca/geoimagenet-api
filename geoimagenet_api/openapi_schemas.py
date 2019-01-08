from typing import List
from datetime import datetime

from dataclasses import dataclass, field


class Optional:
    pass


@dataclass
class ApiInfo:
    name: str
    version: str
    authors: str
    email: str


@dataclass
class User:
    id: int
    username: str
    name: str


@dataclass
class TaxonomyClass:
    id: int
    name: str
    taxonomy_group_id: int
    children: List["TaxonomyClass"] = field(default=Optional)


@dataclass
class TaxonomyGroup:
    id: int
    name: str
    version: str


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
