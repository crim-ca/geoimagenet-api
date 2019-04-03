"""10_annotation_friendly_name

Revision ID: 2dd1abf5cb94
Revises: f0eb712a7220
Create Date: 2019-03-28 21:47:42.541263

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = '2dd1abf5cb94'
down_revision = 'f0eb712a7220'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('annotation', sa.Column('name', sa.String(), server_default="NONE", nullable=False))
    op.add_column('taxonomy_class', sa.Column('code', sa.String(), server_default="NONE", nullable=False))

    annotation_update_name = """
        CREATE OR REPLACE FUNCTION annotation_update_name() RETURNS trigger AS $$ 
            DECLARE
                centroid geometry;
            BEGIN 
                centroid := ST_Transform(ST_Centroid(NEW.geometry), 4326);
                NEW.name := (SELECT COALESCE(code, '') FROM taxonomy_class WHERE id=NEW.taxonomy_class_id) || '_' || 
                            to_char(ST_Y(centroid), 'SG099.999999') || '_' || 
                            to_char(ST_X(centroid), 'SG099.999999');
                RETURN NEW;
            END;
        $$ LANGUAGE 'plpgsql';

        CREATE TRIGGER annotation_name_on_insert BEFORE INSERT ON annotation
        FOR EACH ROW EXECUTE PROCEDURE annotation_update_name();

        CREATE TRIGGER annotation_name_on_update BEFORE UPDATE OF geometry, taxonomy_class_id ON annotation
        FOR EACH ROW EXECUTE PROCEDURE annotation_update_name();
    """

    op.execute(annotation_update_name)

    # trigger annotation name update for existing annotations
    op.execute("UPDATE annotation SET taxonomy_class_id = taxonomy_class_id;")

    # remove temporary server defaults. This is to be able to create a temporary empty nullable column.
    op.alter_column('annotation', 'name', server_default=None)


def downgrade():
    op.drop_column('annotation', 'name')
    op.drop_column('taxonomy_class', 'code')

    op.execute("drop trigger if exists annotation_name_on_insert on annotation cascade;")
    op.execute("drop trigger if exists annotation_name_on_update on annotation cascade;")
