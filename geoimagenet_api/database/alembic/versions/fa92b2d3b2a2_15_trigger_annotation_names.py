"""15_trigger_annotation_names

Revision ID: fa92b2d3b2a2
Revises: d714ede8fd71
Create Date: 2019-08-22 11:24:35.479278

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = 'fa92b2d3b2a2'
down_revision = 'd714ede8fd71'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE annotation SET taxonomy_class_id = taxonomy_class_id")


def downgrade():
    pass
