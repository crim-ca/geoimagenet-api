"""19_add_trace_simplified

Revision ID: 2d7013cf6647
Revises: 8e2e20e10f5b
Create Date: 2019-10-09 09:43:17.093454

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
revision = "2d7013cf6647"
down_revision = "8e2e20e10f5b"
branch_labels = None
depends_on = None

trigger_trace_simplified = """
    CREATE OR REPLACE FUNCTION set_trace_simplified_trigger() RETURNS trigger AS $$ 
        BEGIN 
            IF NEW.trace NOTNULL THEN
                NEW.trace_simplified = st_simplify(NEW.trace, 5);
            END IF;
            RETURN NEW;
        END; 
    $$ LANGUAGE 'plpgsql';

    CREATE TRIGGER trace_simplified_trigger BEFORE INSERT OR UPDATE ON image
    FOR EACH ROW EXECUTE PROCEDURE set_trace_simplified_trigger();
"""


def upgrade():
    op.add_column(
        "image",
        sa.Column(
            "trace_simplified",
            geoalchemy2.types.Geometry(
                geometry_type="POLYGON", srid=3857, spatial_index=False
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_image_trace_simplified",
        "image",
        ["trace_simplified"],
        unique=False,
        postgresql_using="gist",
    )

    op.execute(trigger_trace_simplified)


def downgrade():
    op.drop_index("idx_image_trace_simplified", table_name="image")
    op.drop_column("image", "trace_simplified")

    op.execute("drop trigger if exists trace_simplified_trigger on image cascade;")
