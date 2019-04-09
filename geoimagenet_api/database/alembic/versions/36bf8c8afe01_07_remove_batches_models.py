"""07_remove_batches_models

Revision ID: 36bf8c8afe01
Revises: dd4da5361979
Create Date: 2019-02-20 16:19:12.747404

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '36bf8c8afe01'
down_revision = 'dd4da5361979'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('batch_item')
    op.drop_table('batch')


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('batch',
    sa.Column('id', sa.INTEGER(), server_default=sa.text("nextval('batch_id_seq'::regclass)"), autoincrement=True, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('validation_rules_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('created_by', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('taxonomy_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['person.id'], name='batch_person_id_fkey'),
    sa.ForeignKeyConstraint(['taxonomy_id'], ['taxonomy.id'], name='batch_taxonomy_id_fkey', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['validation_rules_id'], ['validation_rules.id'], name='batch_validation_rules_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='batch_pkey'),
    postgresql_ignore_search_path=False
    )
    op.create_index('ix_batch_created_by', 'batch', ['created_by'], unique=False)
    op.create_table('batch_item',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('batch_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('annotation_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('role', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['annotation_id'], ['annotation.id'], name='batch_item_annotation_id_fkey'),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], name='batch_item_batch_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='batch_item_pkey')
    )
    op.create_index('ix_batch_item_role', 'batch_item', ['role'], unique=False)
    op.create_index('ix_batch_item_batch_id', 'batch_item', ['batch_id'], unique=False)
    # ### end Alembic commands ###
