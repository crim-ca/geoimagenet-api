"""20_allow_null_image_id

Revision ID: 6d80bc41d745
Revises: 2d7013cf6647
Create Date: 2019-10-17 17:13:10.316082

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = '6d80bc41d745'
down_revision = '2d7013cf6647'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('annotation', 'image_id',
               existing_type=sa.INTEGER(),
               nullable=True)


def downgrade():
    op.alter_column('annotation', 'image_id',
               existing_type=sa.INTEGER(),
               nullable=False)
