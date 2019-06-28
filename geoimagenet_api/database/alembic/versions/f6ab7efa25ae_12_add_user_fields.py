"""12_add_user_fields

Revision ID: f6ab7efa25ae
Revises: a8fd058f13eb
Create Date: 2019-06-14 15:14:34.844800

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = 'f6ab7efa25ae'
down_revision = 'a8fd058f13eb'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_image_layer_name'), 'image', ['layer_name'], unique=False)
    op.drop_index('ix_image_name', table_name='image')

    op.add_column('person', sa.Column('email', sa.String(), nullable=True))
    op.add_column('person', sa.Column('firstname', sa.String(), nullable=True))
    op.add_column('person', sa.Column('lastname', sa.String(), nullable=True))
    op.add_column('person', sa.Column('organisation', sa.String(), nullable=True))
    op.drop_column('person', 'name')


def downgrade():
    op.add_column('person', sa.Column('name', sa.VARCHAR(), autoincrement=False))
    op.drop_column('person', 'organisation')
    op.drop_column('person', 'lastname')
    op.drop_column('person', 'firstname')
    op.drop_column('person', 'email')

    op.create_index('ix_image_name', 'image', ['layer_name'], unique=False)
    op.drop_index(op.f('ix_image_layer_name'), table_name='image')
