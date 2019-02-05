"""04_batches

Revision ID: 9c54b04e3033
Revises: fba33e3dbe70
Create Date: 2019-02-04 23:30:04.238235

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = '9c54b04e3033'
down_revision = 'fba33e3dbe70'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_annotation_log_operation'), 'annotation_log', ['operation'], unique=False)
    op.add_column('batch', sa.Column('created_by', sa.Integer(), nullable=True))
    op.add_column('batch', sa.Column('taxonomy_id', sa.Integer(), nullable=False))
    op.create_index(op.f('ix_batch_created_by'), 'batch', ['created_by'], unique=False)
    op.create_foreign_key('batch_person_id_fkey', 'batch', 'person', ['created_by'], ['id'])
    op.create_index(op.f('ix_batch_item_batch_id'), 'batch_item', ['batch_id'], unique=False)
    op.create_index(op.f('ix_batch_item_role'), 'batch_item', ['role'], unique=False)
    op.drop_constraint('batch_item_batch_id_fkey', 'batch_item', type_='foreignkey')
    op.create_foreign_key('batch_item_batch_id_fkey', 'batch_item', 'batch', ['batch_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('batch_taxonomy_id_fkey', 'batch', 'taxonomy', ['taxonomy_id'], ['id'], ondelete='CASCADE')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('batch_item_batch_id_fkey', 'batch_item', type_='foreignkey')
    op.drop_constraint('batch_taxonomy_id_fkey', 'batch', type_='foreignkey')
    op.create_foreign_key('batch_item_batch_id_fkey', 'batch_item', 'batch', ['batch_id'], ['id'])
    op.drop_index(op.f('ix_batch_item_role'), table_name='batch_item')
    op.drop_index(op.f('ix_batch_item_batch_id'), table_name='batch_item')
    op.drop_constraint('batch_person_id_fkey', 'batch', type_='foreignkey')
    op.drop_index(op.f('ix_batch_created_by'), table_name='batch')
    op.drop_column('batch', 'created_by')
    op.drop_column('batch', 'taxonomy_id')
    op.drop_index(op.f('ix_annotation_log_operation'), table_name='annotation_log')
    # ### end Alembic commands ###
