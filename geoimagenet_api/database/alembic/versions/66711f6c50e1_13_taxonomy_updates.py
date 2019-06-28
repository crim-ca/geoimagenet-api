"""13_taxonomy_updates

Revision ID: 66711f6c50e1
Revises: f6ab7efa25ae
Create Date: 2019-06-26 17:01:48.133499

"""
import json
import re
from itertools import permutations
from pathlib import Path
from typing import Iterable

import unidecode
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.expression import bindparam

# revision identifiers, used by Alembic.
revision = "66711f6c50e1"
down_revision = "f6ab7efa25ae"
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

taxonomy = sa.table(
    "taxonomy",
    sa.column("id", sa.Integer),
    sa.column("name_fr", sa.String),
    sa.column("name_en", sa.String),
    sa.column("version", sa.String),
)

annotation = sa.table("annotation", sa.column("taxonomy_class_id", sa.Integer))

annotation_log = sa.table("annotation_log", sa.column("taxonomy_class_id", sa.Integer))


def make_codes_from_name(name: str) -> Iterable[str]:
    """A generator that takes a french name and generates a list of 4-letter code possibilities.

    Keep the first letter and permute all the others.
    If name is smaller than 4 characters, duplicate the last letter.
    """
    if not name:
        return ValueError("'name' must not be empty")

    # remove accents, capitalize
    name = unidecode.unidecode(name).upper()
    # remove non A-Z characters
    name = "".join(re.findall(r"[A-Z]", name))

    while not len(name) >= 4:
        name += name[-1]

    for permutation in permutations(name[1:], 3):
        yield name[0] + "".join(permutation)


def upgrade():
    # ------
    # Create codes for taxonomy classes
    # ------

    conn = op.get_bind()

    # ------
    # Generate codes for taxonomy classes in database

    query = sa.select(
        [
            taxonomy_class.c.id,
            taxonomy_class.c.name_fr,
            taxonomy_class.c.name_en,
            taxonomy_class.c.code,
        ]
    ).order_by(taxonomy_class.c.id)
    taxonomy_classes = conn.execute(query).fetchall()

    if taxonomy_classes:
        all_codes = set()
        ids_with_codes = []

        for id_, name_fr, name_en, old_code in taxonomy_classes:

            if old_code and old_code != "NONE" and old_code not in all_codes:
                # keep old code if it exists
                ids_with_codes.append({"id_": id_, "code": old_code})
                all_codes.add(old_code)
                continue

            if not name_fr and not name_en:
                raise ValueError("Taxonomy class in database without names.")
            name = name_en or name_fr  # english by default
            for code in make_codes_from_name(name):
                if code not in all_codes:
                    ids_with_codes.append({"id_": id_, "code": code})
                    all_codes.add(code)
                    break
            else:
                raise RuntimeError(f"Couldn't generate unique code for '{name_fr}'")
        if not len(ids_with_codes) == len(taxonomy_classes) == len(all_codes):
            raise RuntimeError("Taxonomy codes were not generated correctly.")

        # Write codes to the database
        stmt = (
            taxonomy_class.update()
            .where(taxonomy_class.c.id == bindparam("id_"))
            .values({"code": bindparam("code")})
        )

        conn.execute(stmt, ids_with_codes)

        # ------
        # add 3 missing taxonomy classes
        missing_classes = [
            {
                "parent_code": "COMC",
                "taxonomy_id": 2,
                "name_fr": "Campus (université ou collège)",
                "name_en": "Campus (university or college)",
                "code": "CAMP",
            },
            {
                "parent_code": "WETA",
                "taxonomy_id": 2,
                "name_fr": "Eau peu profonde",
                "name_en": "Shallow water",
                "code": "SHAW",
            },
            {
                "parent_code": "TRAI",
                "taxonomy_id": 1,
                "name_fr": "Passage à niveau",
                "name_en": "Railway crossing",
                "code": "RAIC",
            },
        ]

        for taxo in missing_classes:
            parent_id = conn.execute(
                sa.select([taxonomy_class.c.id]).where(
                    taxonomy_class.c.code == taxo["parent_code"]
                )
            ).fetchone()[0]
            conn.execute(
                sa.insert(taxonomy_class).values(
                    {
                        "parent_id": parent_id,
                        "taxonomy_id": taxo["taxonomy_id"],
                        "code": taxo["code"],
                        "name_fr": taxo["name_fr"],
                        "name_en": taxo["name_en"],
                    }
                )
            )

        # ------
        # remove "Énergie verte"

        energie_id = conn.execute(
            sa.select([taxonomy_class.c.id]).where(taxonomy_class.c.code == "ENEG")
        ).fetchone()[0]
        query = sa.select([taxonomy_class.c.id]).where(
            (taxonomy_class.c.id == energie_id) | (taxonomy_class.c.parent_id == energie_id)
        )
        ids_to_delete = [r.id for r in conn.execute(query)]
        print(ids_to_delete)

        conn.execute(
            sa.delete(annotation_log).where(
                annotation_log.c.taxonomy_class_id.in_(ids_to_delete)
            )
        )
        conn.execute(
            sa.delete(annotation).where(annotation.c.taxonomy_class_id.in_(ids_to_delete))
        )
        conn.execute(
            sa.delete(taxonomy_class).where(taxonomy_class.c.id.in_(ids_to_delete))
        )

        # # ------
        # # make sure names are ok according to json
        data = []

        def recurse_json(tree, taxonomy_id):
            taxo = conn.execute(
                sa.select(
                    [
                        taxonomy_class.c.id,
                        taxonomy_class.c.name_fr,
                        taxonomy_class.c.name_en,
                        taxonomy_class.c.code,
                    ]
                )
                .where(taxonomy_class.c.code == tree["code"])
                .where(taxonomy_class.c.taxonomy_id == taxonomy_id)
            ).fetchone()
            if not taxo:
                print(tree["code"], taxonomy_id)
            data.append(
                {
                    "id_": taxo.id,
                    "name_fr": tree["name"]["fr"],
                    "name_en": tree["name"]["en"],
                }
            )
            for child in tree.get("value", []):
                recurse_json(child, taxonomy_id)

        for file, taxonomy_id in zip(["objets.json", "couverture_de_sol.json"], [1, 2]):
            json_data = Path(__file__).parent.parent.parent / "json_data"
            recurse_json(json.loads((json_data / file).read_text()), taxonomy_id)

        stmt = (
            taxonomy_class.update()
            .where(taxonomy_class.c.id == bindparam("id_"))
            .values({"name_fr": bindparam("name_fr"), "name_en": bindparam("name_en")})
        )
        conn.execute(stmt, data)

        conn.execute(
            taxonomy.update().where(taxonomy.c.id == 2).values({"name_en": "Land cover"})
        )

    # ------
    # Constraints
    # ------
    op.drop_index("ix_taxonomy_class_code", table_name="taxonomy_class")
    op.create_index(
        op.f("ix_taxonomy_class_code"), "taxonomy_class", ["code"], unique=True
    )
    op.alter_column('taxonomy_class', 'code', server_default=None)


def downgrade():
    # ------
    # Constraints
    # ------
    op.drop_index(op.f("ix_taxonomy_class_code"), table_name="taxonomy_class")
    op.create_index("ix_taxonomy_class_code", "taxonomy_class", ["code"], unique=False)
    op.alter_column('taxonomy_class', 'code', server_default="NONE")

    conn = op.get_bind()

    # ------
    # Remove or add the data back

    conn.execute(
        sa.delete(taxonomy_class).where(
            taxonomy_class.c.code.in_(["SHAW", "CAMP", "RAIC"])
        )
    )

    values = [
        {
            "id": 194,  # We can do that, because the id was always the same before this migration
            "parent_id": 1,
            "taxonomy_id": 1,
            "code": "ENEG",
            "name_fr": "Énergie verte",
        },
        {
            "id": 195,
            "taxonomy_id": 1,
            "parent_id": 194,
            "code": "NONE",
            "name_fr": "Roofedge - toit vert",
        },
        {
            "id": 196,
            "taxonomy_id": 1,
            "parent_id": 194,
            "code": "NONE",
            "name_fr": "Roofedge - avec panneau solaire",
        },
        {
            "id": 197,
            "taxonomy_id": 1,
            "parent_id": 194,
            "code": "NONE",
            "name_fr": "Toit plat",
        },
        {
            "id": 198,
            "taxonomy_id": 1,
            "parent_id": 194,
            "code": "NONE",
            "name_fr": "Toit plat < 10 % obstruction",
        },
        {
            "id": 199,
            "taxonomy_id": 1,
            "parent_id": 194,
            "code": "NONE",
            "name_fr": "Toit plat  10 - 30% obstruction",
        },
        {
            "id": 200,
            "taxonomy_id": 1,
            "parent_id": 194,
            "code": "NONE",
            "name_fr": "Toit plat > 30 % obstruction",
        },
        {
            "id": 201,
            "taxonomy_id": 1,
            "code": "NONE",
            "parent_id": 194,
            "name_fr": "Toit 2 pentes",
        },
        {
            "id": 202,
            "taxonomy_id": 1,
            "code": "NONE",
            "parent_id": 194,
            "name_fr": "Toit 4 pentes",
        },
        {
            "id": 203,
            "taxonomy_id": 1,
            "code": "NONE",
            "parent_id": 194,
            "name_fr": "Toit complexe",
        },
        {
            "id": 204,
            "taxonomy_id": 1,
            "code": "NONE",
            "parent_id": 194,
            "name_fr": "Toit convexe",
        },
    ]

    op.bulk_insert(taxonomy_class, values)
