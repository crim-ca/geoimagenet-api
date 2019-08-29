"""16_add_user_followers

Revision ID: 55ada59cedd9
Revises: fa92b2d3b2a2
Create Date: 2019-08-27 16:41:10.050352

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
revision = "55ada59cedd9"
down_revision = "fa92b2d3b2a2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "person_follower",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("follow_user_id", sa.Integer(), nullable=False),
        sa.Column("nickname", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("person_follower")
