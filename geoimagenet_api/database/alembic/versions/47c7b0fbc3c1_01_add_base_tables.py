"""01_add_base_tables

Revision ID: 47c7b0fbc3c1
Revises: 
Create Date: 2019-01-09 13:21:26.978092

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = '47c7b0fbc3c1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('annotation_log_description',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('person',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_table('taxonomy',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('version', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'version', name='uc_taxonomy')
    )
    op.create_table('validation_rules',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nb_validators', sa.Integer(), server_default='0', nullable=False),
    sa.Column('consensus', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('batch',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('validation_rules_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['validation_rules_id'], ['validation_rules.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('taxonomy_class',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('taxonomy_id', sa.Integer(), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['parent_id'], ['taxonomy_class.id'], ),
    sa.ForeignKeyConstraint(['taxonomy_id'], ['taxonomy.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('parent_id', 'name', name='uc_taxonomy_class')
    )
    op.create_table('annotation',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('annotator_id', sa.Integer(), nullable=False),
    sa.Column('geometry', geoalchemy2.types.Geometry(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
    sa.Column('taxonomy_class_id', sa.Integer(), nullable=False),
    sa.Column('image_name', sa.String(), nullable=False),
    sa.Column('released', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.ForeignKeyConstraint(['annotator_id'], ['person.id'], ),
    sa.ForeignKeyConstraint(['taxonomy_class_id'], ['taxonomy_class.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('annotation_log',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('annotation_id', sa.Integer(), nullable=True),
    sa.Column('annotator_id', sa.Integer(), nullable=True),
    sa.Column('geometry', geoalchemy2.types.Geometry(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
    sa.Column('taxonomy_class_id', sa.Integer(), nullable=True),
    sa.Column('image_name', sa.String(), nullable=True),
    sa.Column('released', sa.Boolean(), nullable=True),
    sa.Column('description', sa.Integer(), server_default='1', nullable=True),
    sa.ForeignKeyConstraint(['annotation_id'], ['annotation.id'], ),
    sa.ForeignKeyConstraint(['annotator_id'], ['person.id'], ),
    sa.ForeignKeyConstraint(['description'], ['annotation_log_description.id'], ),
    sa.ForeignKeyConstraint(['taxonomy_class_id'], ['taxonomy_class.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('batch_item',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('annotation_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['annotation_id'], ['annotation.id'], ),
    sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('validation_event',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('annotation_id', sa.Integer(), nullable=False),
    sa.Column('validator_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
    sa.ForeignKeyConstraint(['annotation_id'], ['annotation.id'], ),
    sa.ForeignKeyConstraint(['validator_id'], ['person.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('validation_event')
    op.drop_table('batch_item')
    op.drop_table('annotation_log')
    op.drop_table('annotation')
    op.drop_table('taxonomy_class')
    op.drop_table('batch')
    op.drop_table('validation_rules')
    op.drop_table('taxonomy')
    op.drop_table('person')
    op.drop_table('annotation_log_description')
    # ### end Alembic commands ###
