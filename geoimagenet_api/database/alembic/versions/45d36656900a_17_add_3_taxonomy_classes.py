"""17_add_2_taxonomy_classes

Revision ID: 45d36656900a
Revises: 55ada59cedd9
Create Date: 2019-09-12 13:44:31.026672

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "45d36656900a"
down_revision = "55ada59cedd9"
branch_labels = None
depends_on = None

taxonomy_class = sa.table(
    "taxonomy_class",
    sa.column("id", sa.Integer),
    sa.column("taxonomy_id", sa.Integer),
    sa.column("parent_id", sa.Integer),
    sa.column("name_fr", sa.String),
    sa.column("name_en", sa.String),
    sa.column("code", sa.String),
)


def upgrade():
    conn = op.get_bind()

    objects_id = sa.select([taxonomy_class.c.id]).where(
        taxonomy_class.c.name_en == "Objects"
    )
    objets_taxonomy_id = sa.select([taxonomy_class.c.taxonomy_id]).where(
        taxonomy_class.c.name_en == "Objects"
    )
    # ------
    # insert
    # ------
    """ Objet (Object)
         -> Milieu humide (Wetland)
             -> Tourbière exploitée (Commercial fen)
    """
    wetland_id = (
        sa.select([taxonomy_class.c.id])
        .where(taxonomy_class.c.parent_id == objects_id)
        .where(taxonomy_class.c.name_en == "Wetland")
    )
    conn.execute(
        sa.insert(taxonomy_class).values(
            {
                "parent_id": wetland_id,
                "taxonomy_id": objets_taxonomy_id,
                "code": "COMF",
                "name_fr": "Tourbière exploitée",
                "name_en": "Commercial fen",
            }
        )
    )

    # ------
    # insert
    # ------
    """ Objet (Object)
         -> Infrastructure de transport routier (Road infrastructure)
             -> Piste cyclable (Bike path)
             -> Sentier piétionnier (Pedestrian path)
    """
    road_infrastructure_id = (
        sa.select([taxonomy_class.c.id])
        .where(taxonomy_class.c.parent_id == objects_id)
        .where(taxonomy_class.c.name_en == "Road infrastructure")
    )
    conn.execute(
        sa.insert(taxonomy_class).values(
            {
                "parent_id": road_infrastructure_id,
                "taxonomy_id": objets_taxonomy_id,
                "code": "BIKE",
                "name_fr": "Piste cyclable",
                "name_en": "Bike path",
            }
        )
    )
    conn.execute(
        sa.insert(taxonomy_class).values(
            {
                "parent_id": road_infrastructure_id,
                "taxonomy_id": objets_taxonomy_id,
                "code": "PATH",
                "name_fr": "Sentier piétonnier",
                "name_en": "Pedestrian path",
            }
        )
    )

    # fix Cemetary -> Cemetery
    conn.execute(
        taxonomy_class.update()
        .where(taxonomy_class.c.name_en == "Cemetary")
        .values({"name_en": "Cemetery"})
    )


def downgrade():
    conn = op.get_bind()

    conn.execute(
        sa.delete(taxonomy_class).where(
            taxonomy_class.c.name_en.in_(
                ["Bike path", "Pedestrian path", "Commercial fen"]
            )
        )
    )
    conn.execute(
        taxonomy_class.update()
        .where(taxonomy_class.c.name_en == "Cemetery")
        .values({"name_en": "Cemetary"})
    )
