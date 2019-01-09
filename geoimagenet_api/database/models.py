from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    text,
    Boolean,
    UniqueConstraint,
)
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


class Annotation(Base):
    __tablename__ = "annotation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    annotator_id = Column(Integer, ForeignKey("person.id"), nullable=False)
    geometry = Column(Geometry("GEOMETRY"), nullable=False)
    updated_at = Column(DateTime, server_default=text("NOW()"), nullable=False)
    taxonomy_class_id = Column(Integer, ForeignKey("taxonomy_class.id"), nullable=False)
    image_name = Column(String, nullable=False)
    released = Column(
        Boolean, default=False, server_default=expression.false(), nullable=False
    )


class AnnotationLogDescription(Base):
    __tablename__ = "annotation_log_description"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)


class AnnotationLog(Base):
    __tablename__ = "annotation_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    annotation_id = Column(Integer, ForeignKey("annotation.id"))
    annotator_id = Column(Integer, ForeignKey("person.id"))
    geometry = Column(Geometry("GEOMETRY"))
    created_at = Column(DateTime, server_default=text("NOW()"))
    taxonomy_class_id = Column(Integer, ForeignKey("taxonomy_class.id"))
    image_name = Column(String)
    released = Column(Boolean)
    description = Column(
        Integer, ForeignKey("annotation_log_description.id"), server_default="1"
    )


class Batch(Base):
    __tablename__ = "batch"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)
    validation_rules_id = Column(
        Integer, ForeignKey("validation_rules.id"), nullable=False
    )
    batch_items = relationship(
        "BatchItem", back_populates="batch", cascade="all, delete, delete-orphan"
    )


class BatchItem(Base):
    __tablename__ = "batch_item"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("batch.id"), nullable=False)
    batch = relationship("Batch", back_populates="batch_items")
    annotation_id = Column(Integer, ForeignKey("annotation.id"), nullable=False)
    role = Column(String, nullable=False)


class ValidationRules(Base):
    __tablename__ = "validation_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nb_validators = Column(Integer, server_default="0", nullable=False)
    consensus = Column(Boolean, server_default=expression.true(), nullable=False)


class TaxonomyClass(Base):
    __tablename__ = "taxonomy_class"

    id = Column(Integer, primary_key=True, autoincrement=True)
    taxonomy_id = Column(Integer, ForeignKey("taxonomy.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("taxonomy_class.id"))
    children = relationship(
        "TaxonomyClass", backref=backref("parent", remote_side=[id])
    )
    name = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("parent_id", "name", name="uc_taxonomy_class"),)


class Taxonomy(Base):
    __tablename__ = "taxonomy"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("name", "version", name="uc_taxonomy"),)


class ValidationEvent(Base):
    __tablename__ = "validation_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    annotation_id = Column(Integer, ForeignKey("annotation.id"), nullable=False)
    validator_id = Column(Integer, ForeignKey("person.id"), nullable=False)
    validator = relationship("Person")
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)
