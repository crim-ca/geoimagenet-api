"""09_add_taxonomy_class_languages

Revision ID: f0eb712a7220
Revises: fa165ad14f9f
Create Date: 2019-03-20 15:43:58.770114

"""
import json
from pathlib import Path

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column, select
from sqlalchemy import String, Integer
import geoalchemy2


# revision identifiers, used by Alembic.
revision = "f0eb712a7220"
down_revision = "fa165ad14f9f"
branch_labels = None
depends_on = None

taxonomy_class = table(
    "taxonomy_class",
    column("id", Integer),
    column("taxonomy_id", Integer),
    column("parent_id", Integer),
    column("name_fr", String),
    column("name_en", String),
)

taxonomy = table(
    "taxonomy",
    column("id", Integer),
    column("name_fr", String),
    column("name_en", String),
    column("version", String),
)


def upgrade():
    # rename columns
    op.alter_column("taxonomy", "name", nullable=False, new_column_name="name_fr")
    op.alter_column("taxonomy_class", "name", nullable=False, new_column_name="name_fr")
    op.execute('DROP INDEX IF EXISTS ix_taxonomy_class_name;')
    op.create_index(
        op.f("ix_taxonomy_class_name_fr"), "taxonomy_class", ["name_fr"], unique=False
    )

    # add columns
    op.add_column("taxonomy", sa.Column("name_en", sa.String(), nullable=True))
    op.add_column("taxonomy_class", sa.Column("name_en", sa.String(), nullable=True))
    op.create_index(
        op.f("ix_taxonomy_class_name_en"), "taxonomy_class", ["name_en"], unique=False
    )

    # ------------------
    # Migrate taxonomy data if it exists
    # ------------------

    def recurse_json(obj, taxonomy_class_id):
        """Recurse the json document and add french and english names.

        The json structure and elements order didn't change.
        So as long as we recurse the elements in the same way as the data import script,
        it's safe to assume the indices are in the same order."""
        op.execute(
            taxonomy_class.update()
            .where(taxonomy_class.c.id == taxonomy_class_id)
            .values({"name_fr": obj["name"]["fr"], "name_en": obj["name"]["en"] or None})
        )

        taxonomy_class_id += 1

        if "value" in obj:
            for o in obj["value"]:
                taxonomy_class_id = recurse_json(o, taxonomy_class_id)

        return taxonomy_class_id

    objets_json_path = Path(__file__).parent.parent.parent / "json_data" / "objets_v1_a.json"
    objets_data = json.loads(objets_json_path.read_text())

    name_fr = objets_data["name"]["fr"]
    version = objets_data["version"]

    # check if there is taxonomy data
    conn = op.get_bind()
    result = conn.execute(
        select([taxonomy.c.id])
        .where(taxonomy.c.version == str(version))
        .where(taxonomy.c.name_fr == name_fr)
    ).fetchone()

    if result:
        taxonomy_id = result[0]
        result = conn.execute(
            select([taxonomy_class.c.id])
            .where(taxonomy_class.c.taxonomy_id == taxonomy_id)
            .where(taxonomy_class.c.parent_id.is_(None))
        ).fetchone()
        if result:
            taxonomy_class_root = result[0]
            recurse_json(objets_data, taxonomy_class_root)

            # set taxonomy name_en
            name_en = objets_data["name"]["en"]
            if name_en:
                op.execute(
                    taxonomy.update()
                    .where(taxonomy.c.id == taxonomy_id)
                    .values({"name_en": name_en})
                )

    # remove temporary server defaults. This is to be able to create an empty nullable column.
    op.alter_column('taxonomy', 'name_en', server_default=None)
    op.alter_column('taxonomy_class', 'name_en', server_default=None)

    op.drop_constraint('uc_taxonomy_class', 'taxonomy_class')
    op.create_unique_constraint('uc_taxonomy_class', 'taxonomy_class', ["parent_id", "name_fr"])

    op.drop_constraint('uc_taxonomy', 'taxonomy')
    op.create_unique_constraint('uc_taxonomy', 'taxonomy', ["version", "name_fr"])


def downgrade():
    # rename columns
    op.alter_column("taxonomy", "name_fr", nullable=False, new_column_name="name")
    op.alter_column("taxonomy_class", "name_fr", nullable=False, new_column_name="name")
    op.execute('DROP INDEX IF EXISTS ix_taxonomy_class_name_fr;')
    op.create_index(
        op.f("ix_taxonomy_class_name"), "taxonomy_class", ["name"], unique=False
    )

    # remove columns
    op.drop_column("taxonomy_class", "name_en")
    op.drop_column("taxonomy", "name_en")

    op.drop_constraint('uc_taxonomy_class', 'taxonomy_class')
    op.create_unique_constraint('uc_taxonomy_class', 'taxonomy_class', ["parent_id", "name"])

    op.drop_constraint('uc_taxonomy', 'taxonomy')
    op.create_unique_constraint('uc_taxonomy', 'taxonomy', ["version", "name"])
