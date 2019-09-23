"""18_add_image_trace

Revision ID: 8e2e20e10f5b
Revises: 45d36656900a
Create Date: 2019-09-23 09:41:29.503742

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = "8e2e20e10f5b"
down_revision = "45d36656900a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "image",
        sa.Column(
            "trace",
            geoalchemy2.types.Geometry(geometry_type="POLYGON", srid=3857),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_image_trace", "image", ["trace"], unique=False, postgresql_using="gist"
    )


def downgrade():
    op.drop_index("idx_image_trace", table_name="image")
    op.drop_column("image", "trace")
