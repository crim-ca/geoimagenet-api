"""05_validation_value

Revision ID: dd4da5361979
Revises: 9c54b04e3033
Create Date: 2019-02-08 11:25:38.404528

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'dd4da5361979'
down_revision = '9c54b04e3033'
branch_labels = None
depends_on = None

validation_statuses = ("validated", "rejected")


def upgrade():
    # ---------
    # Create enum
    # ---------
    annotation_status_enum = postgresql.ENUM(*validation_statuses, name="validation_value_enum")
    annotation_status_enum.create(op.get_bind())

    # ---------
    # Add columns
    # ---------
    op.add_column('validation_event', sa.Column('validation_value', sa.Enum('validated', 'rejected', name='validation_value_enum'), nullable=False))
    op.create_index(op.f('ix_validation_event_validation_value'), 'validation_event', ['validation_value'], unique=False)


def downgrade():
    # ---------
    # Drop columns
    # ---------
    op.drop_index(op.f('ix_validation_event_validation_value'), table_name='validation_event')
    op.drop_column('validation_event', 'validation_value')

    # ---------
    # Drop enum
    # ---------
    op.execute("DROP TYPE validation_value_enum;")
