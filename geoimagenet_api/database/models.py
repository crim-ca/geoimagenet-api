import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    text,
    Boolean,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy import Enum
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import expression
from geoalchemy2 import Geometry

Base = declarative_base()


class Person(Base):
    __tablename__ = "person"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)


class AnnotationStatus(enum.Enum):
    new = 1
    pre_released = 2
    released = 3
    review = 4
    validated = 5
    rejected = 6
    deleted = 7


class Annotation(Base):
    __tablename__ = "annotation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    annotator_id = Column(Integer, ForeignKey("person.id"), nullable=False, index=True)
    geometry = Column(
        Geometry("GEOMETRY", srid=3857, spatial_index=False), nullable=False
    )
    updated_at = Column(DateTime, server_default=text("NOW()"), nullable=False)
    taxonomy_class_id = Column(
        Integer, ForeignKey("taxonomy_class.id"), nullable=False, index=True
    )
    image_name = Column(String, nullable=False)
    status = Column(
        Enum(AnnotationStatus, name="annotation_status_enum"),
        nullable=False,
        index=True,
        server_default=AnnotationStatus.new.name,
    )

    __table_args__ = (
        Index("idx_annotation_geometry", geometry, postgresql_using="gist"),
    )


class AnnotationLogOperation(enum.Enum):
    insert = 1
    update = 2
    delete = 3


class AnnotationLog(Base):
    __tablename__ = "annotation_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    annotation_id = Column(Integer, nullable=False, index=True)
    annotator_id = Column(Integer, ForeignKey("person.id"), index=True)
    geometry = Column(Geometry("GEOMETRY", srid=3857, spatial_index=False))
    created_at = Column(DateTime, server_default=text("NOW()"))
    taxonomy_class_id = Column(Integer, ForeignKey("taxonomy_class.id"), index=True)
    image_name = Column(String)
    status = Column(Enum(AnnotationStatus, name="annotation_status_enum"), index=True)
    operation = Column(
        Enum(AnnotationLogOperation, name="annotation_log_operation_enum"),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("idx_annotation_log_geometry", geometry, postgresql_using="gist"),
    )


class Batch(Base):
    __tablename__ = "batch"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)
    created_by = Column(Integer, ForeignKey("person.id"), index=True)
    taxonomy_id = Column(Integer, ForeignKey("taxonomy.id", ondelete="CASCADE"), nullable=False)
    validation_rules_id = Column(
        Integer, ForeignKey("validation_rules.id"), nullable=False
    )
    batch_items = relationship(
        "BatchItem", back_populates="batch", passive_deletes=True
    )


class BatchItem(Base):
    __tablename__ = "batch_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(
        Integer, ForeignKey("batch.id", ondelete="CASCADE"), nullable=False, index=True
    )
    annotation_id = Column(Integer, ForeignKey("annotation.id"), nullable=False)
    role = Column(String, nullable=False, index=True)
    batch = relationship("Batch", back_populates="batch_items")


class ValidationRules(Base):
    __tablename__ = "validation_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nb_validators = Column(Integer, server_default="0", nullable=False)
    consensus = Column(Boolean, server_default=expression.true(), nullable=False)


class TaxonomyClass(Base):
    __tablename__ = "taxonomy_class"

    id = Column(Integer, primary_key=True, autoincrement=True)
    taxonomy_id = Column(Integer, ForeignKey("taxonomy.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("taxonomy_class.id"), index=True)
    children = relationship(
        "TaxonomyClass", backref=backref("parent", remote_side=[id])
    )
    name = Column(String, nullable=False, index=True)
    __table_args__ = (UniqueConstraint("parent_id", "name", name="uc_taxonomy_class"),)


class Taxonomy(Base):
    __tablename__ = "taxonomy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("name", "version", name="uc_taxonomy"),)


class ValidationValue(enum.Enum):
    validated = 1
    rejected = 2


class ValidationEvent(Base):
    __tablename__ = "validation_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    annotation_id = Column(Integer, ForeignKey("annotation.id"), nullable=False)
    validator_id = Column(Integer, ForeignKey("person.id"), nullable=False)
    validator = relationship("Person")
    validation_value = Column(
        Enum(ValidationValue, name="validation_value_enum"), nullable=False, index=True
    )
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)


class SpatialRefSys(Base):
    """This class is mostly present to help `alembic revision --autogenerate`

    When it's not here, alembic suggests deleting this table.
    It's not actually used anywhere in geoimagenet_api.
    """
    __tablename__ = "spatial_ref_sys"

    srid = Column(Integer, primary_key=True, autoincrement=False, nullable=False)
    auth_name = Column(String(length=256), nullable=True)
    auth_srid = Column(Integer, nullable=True)
    srtext = Column(String(length=2048), nullable=True)
    proj4text = Column(String(length=2048), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(srid > 0) AND (srid <= 998999)", name="spatial_ref_sys_srid_check"
        ),
    )
