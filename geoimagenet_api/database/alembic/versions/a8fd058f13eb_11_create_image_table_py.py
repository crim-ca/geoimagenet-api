"""11_create_image_table.py

Revision ID: a8fd058f13eb
Revises: 2dd1abf5cb94
Create Date: 2019-04-05 13:29:25.105437

"""
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy import table, Integer, String, column, select, func, and_

# revision identifiers, used by Alembic.
revision = "a8fd058f13eb"
down_revision = "2dd1abf5cb94"
branch_labels = None
depends_on = None

annotation = table(
    "annotation", column("image_id", Integer), column("image_name", String)
)

annotation_log = table(
    "annotation_log", column("image_id", Integer), column("image_name", String)
)

image = table(
    "image",
    column("id", String),
    column("sensor_name", String),
    column("bands", String),
    column("bits", Integer),
    column("filename", String),
    column("extension", String),
)

trigger_annotation_save = """
            CREATE OR REPLACE FUNCTION annotation_save_event() RETURNS trigger AS $$ 
                BEGIN 
                    INSERT INTO annotation_log
                    (annotation_id, annotator_id, geometry, taxonomy_class_id, image_id, status, review_requested, operation)
                    VALUES (
                        NEW.id, 
                        CASE WHEN tg_op = 'INSERT' THEN NEW.annotator_id 
                             WHEN OLD.annotator_id = NEW.annotator_id THEN NULL 
                             ELSE NEW.annotator_id 
                        END, 
                        CASE WHEN tg_op = 'INSERT' THEN NEW.geometry 
                             WHEN st_equals(OLD.geometry, NEW.geometry) THEN NULL 
                             ELSE NEW.geometry 
                        END,
                        CASE WHEN tg_op = 'INSERT' THEN NEW.taxonomy_class_id 
                             WHEN OLD.taxonomy_class_id = NEW.taxonomy_class_id THEN NULL 
                             ELSE NEW.taxonomy_class_id 
                        END,
                        CASE WHEN tg_op = 'INSERT' THEN NEW.image_id 
                             WHEN OLD.image_id = NEW.image_id THEN NULL 
                             ELSE NEW.image_id 
                        END,
                        CASE WHEN tg_op = 'INSERT' THEN NEW.status::annotation_status_enum
                             WHEN OLD.status = NEW.status THEN NULL 
                             ELSE NEW.status 
                        END,
                        CASE WHEN tg_op = 'INSERT' THEN NEW.review_requested
                             WHEN OLD.review_requested = NEW.review_requested THEN NULL 
                             ELSE NEW.review_requested 
                        END,
                        lower(tg_op)::annotation_log_operation_enum
                    );
                    RETURN NEW; 
                END;
            $$ LANGUAGE 'plpgsql';

            CREATE TRIGGER log_annotation_action AFTER INSERT OR UPDATE ON annotation
            FOR EACH ROW EXECUTE PROCEDURE annotation_save_event();
        """

trigger_image_name = """
            CREATE OR REPLACE FUNCTION trigger_image_name() RETURNS trigger AS $$ 
                BEGIN 
                    NEW.sensor_name := UPPER(NEW.sensor_name);
                    NEW.bands := UPPER(NEW.bands);
                    NEW.layer_name := 
                        NEW.sensor_name || '_' || NEW.bands || ':' ||
                        NEW.filename;
                    RETURN NEW; 
                END;
            $$ LANGUAGE 'plpgsql';

            CREATE TRIGGER image_name BEFORE INSERT OR UPDATE ON image
            FOR EACH ROW EXECUTE PROCEDURE trigger_image_name();
        """


def upgrade():
    # ------
    # Create tables
    # ------
    op.create_table(
        "image",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sensor_name", sa.String(), nullable=False),
        sa.Column("bands", sa.String(), nullable=False),
        sa.Column("bits", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("extension", sa.String(), nullable=False),
        sa.Column(
            "layer_name",
            sa.String(),
            nullable=False,
            comment="Must not be set explicitly, this column is updated by a trigger.",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sensor_name", "bands", "bits", "filename", name="uc_image"
        ),
    )
    op.create_index(op.f("ix_image_bands"), "image", ["bands"], unique=False)
    op.create_index(op.f("ix_image_bits"), "image", ["bits"], unique=False)
    op.create_index(op.f("ix_image_extension"), "image", ["extension"], unique=False)
    op.create_index(op.f("ix_image_filename"), "image", ["filename"], unique=False)
    op.create_index(op.f("ix_image_name"), "image", ["layer_name"], unique=False)
    op.create_index(
        op.f("ix_image_sensor_name"), "image", ["sensor_name"], unique=False
    )

    # ------
    # Add Columns
    # ------
    op.add_column("annotation", sa.Column("image_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_annotation_image_id"), "annotation", ["image_id"], unique=False
    )
    op.create_foreign_key(
        "annotation_image_id_fkey", "annotation", "image", ["image_id"], ["id"]
    )
    op.add_column("annotation_log", sa.Column("image_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_annotation_log_image_id"), "annotation_log", ["image_id"], unique=False
    )
    op.create_foreign_key(
        "annotation_log_image_id_fkey", "annotation_log", "image", ["image_id"], ["id"]
    )

    # ---------
    # Triggers
    # ---------
    op.execute("drop trigger if exists log_annotation_action on annotation cascade;")

    op.execute(trigger_annotation_save)
    op.execute(trigger_image_name)

    # ------
    # Migrate data
    # ------
    conn = op.get_bind()

    # extract image info from existing annotations and create information in images table
    images_data = []
    result = conn.execute(select([annotation.c.image_name]).distinct()) or []

    for row in result:
        image_name = row[0]
        if (
            not image_name.count("_") == 9
            or "RGBN" not in image_name
            or "8bit" not in image_name
            or "Pleiades" not in image_name
        ):
            raise ValueError(
                f"Image name is unexpected (fix migration script): {image_name}"
            )
        filename = image_name.split("_", 1)[1]  # example: RGB_filename

        images_data.append(
            {
                "sensor_name": "Pleiades",
                "bands": "RGB",
                "bits": 8,
                "filename": filename,
                "extension": ".tif",
            }
        )

    op.bulk_insert(image, images_data)

    for annotation_table in (annotation, annotation_log):
        subselect = select([image.c.id]).where(
            image.c.filename == func.substr(annotation_table.c.image_name, 5)
        )
        query = annotation_table.update().values({"image_id": subselect})

        conn.execute(query)

    # ------
    # Add null constraints
    # ------
    op.alter_column("annotation", "image_id", nullable=False)

    # ------
    # Drop Columns
    # ------
    op.drop_column("annotation", "image_name")
    op.drop_column("annotation_log", "image_name")

    # add index for taxonomy class code
    op.create_index(
        op.f("ix_taxonomy_class_code"), "taxonomy_class", ["code"], unique=False
    )

    # ------
    # Extension
    # ------
    op.execute("CREATE EXTENSION fuzzystrmatch;")


def downgrade():
    # add index for taxonomy class code
    op.drop_index(op.f("ix_taxonomy_class_code"), table_name="taxonomy_class")

    # ------
    # Add Columns
    # ------
    op.add_column(
        "annotation_log",
        sa.Column("image_name", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "annotation",
        sa.Column("image_name", sa.VARCHAR(), autoincrement=False, nullable=True),
    )

    # ------
    # Migrate data
    # ------
    conn = op.get_bind()

    for annotation_table in (annotation, annotation_log):
        subquery = select([func.concat(image.c.bands, "_", image.c.filename)]).where(
            annotation_table.c.image_id == image.c.id
        )
        conn.execute(annotation_table.update().values({"image_name": subquery}))

    # ------
    # Add null constraints
    # ------
    op.alter_column("annotation", "image_name", nullable=False)

    # ------
    # Drop Columns
    # ------
    op.drop_constraint(
        "annotation_log_image_id_fkey", "annotation_log", type_="foreignkey"
    )
    op.drop_index(op.f("ix_annotation_log_image_id"), table_name="annotation_log")
    op.drop_column("annotation_log", "image_id")
    op.drop_constraint("annotation_image_id_fkey", "annotation", type_="foreignkey")
    op.drop_index(op.f("ix_annotation_image_id"), table_name="annotation")
    op.drop_column("annotation", "image_id")

    # ------
    # Drop Tables
    # ------
    op.drop_index(op.f("ix_image_sensor_name"), table_name="image")
    op.drop_index(op.f("ix_image_name"), table_name="image")
    op.drop_index(op.f("ix_image_filename"), table_name="image")
    op.drop_index(op.f("ix_image_extension"), table_name="image")
    op.drop_index(op.f("ix_image_bits"), table_name="image")
    op.drop_index(op.f("ix_image_bands"), table_name="image")
    op.drop_table("image")

    # ---------
    # Triggers
    # ---------

    op.execute("drop trigger if exists image_name on image cascade;")

    op.execute("drop trigger if exists log_annotation_action on annotation cascade;")
    import sys

    sys.path.append(str(Path(__file__).parent))
    from fba33e3dbe70_03_indices_and_annotation_status import (
        trigger_annotation_save as old_trigger_annotation,
    )

    op.execute(old_trigger_annotation)

    # ------
    # Extension
    # ------
    op.execute("DROP EXTENSION IF EXISTS fuzzystrmatch;")
