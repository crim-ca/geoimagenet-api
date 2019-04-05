"""11_create_image_table.py

Revision ID: a8fd058f13eb
Revises: 2dd1abf5cb94
Create Date: 2019-04-05 13:29:25.105437

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import table, Integer, String, column, select, func

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
    column("rgb_8bit_filename", String),
    column("nrg_8bit_filename", String),
    column("rgbn_8bit_filename", String),
    column("rgbn_16bit_filename", String),
)


def upgrade():
    # ------
    # Create tables
    # ------
    op.create_table(
        "image",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sensor_name", sa.String(), nullable=False),
        sa.Column("rgb_8bit_filename", sa.String(), nullable=True),
        sa.Column("nrg_8bit_filename", sa.String(), nullable=True),
        sa.Column("rgbn_8bit_filename", sa.String(), nullable=True),
        sa.Column("rgbn_16bit_filename", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_image_nrg_8bit_filename"), "image", ["nrg_8bit_filename"], unique=True
    )
    op.create_index(
        op.f("ix_image_rgb_8bit_filename"), "image", ["rgb_8bit_filename"], unique=True
    )
    op.create_index(
        op.f("ix_image_rgbn_16bit_filename"),
        "image",
        ["rgbn_16bit_filename"],
        unique=True,
    )
    op.create_index(
        op.f("ix_image_rgbn_8bit_filename"),
        "image",
        ["rgbn_8bit_filename"],
        unique=True,
    )
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
            raise ValueError(f"Image name is unexpected: {image_name}")
        filename = image_name.split("_", 1)[1]

        images_data.append({"sensor_name": "Pleiades", "rgbn_8bit_filename": filename})

    op.bulk_insert(image, images_data)

    for annotation_table in (annotation, annotation_log):
        subselect = select([image.c.id]).where(
            image.c.rgbn_8bit_filename == func.substr(annotation_table.c.image_name, 5)
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
        subquery = select([func.concat("NRG_", image.c.rgbn_8bit_filename)]).where(
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
    op.drop_index(op.f("ix_image_rgbn_8bit_filename"), table_name="image")
    op.drop_index(op.f("ix_image_rgbn_16bit_filename"), table_name="image")
    op.drop_index(op.f("ix_image_rgb_8bit_filename"), table_name="image")
    op.drop_index(op.f("ix_image_nrg_8bit_filename"), table_name="image")
    op.drop_table("image")
