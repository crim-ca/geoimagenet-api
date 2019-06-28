"""08_add_annotation_review_request

Revision ID: fa165ad14f9f
Revises: 36bf8c8afe01
Create Date: 2019-03-20 12:16:39.931404

"""
from pathlib import Path

from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
revision = "fa165ad14f9f"
down_revision = "36bf8c8afe01"
branch_labels = None
depends_on = None

trigger_annotation_save = """
            CREATE OR REPLACE FUNCTION annotation_save_event() RETURNS trigger AS $$ 
                BEGIN 
                    INSERT INTO annotation_log
                    (annotation_id, annotator_id, geometry, taxonomy_class_id, image_name, status, review_requested, operation)
                    VALUES (
                        NEW.id, 
                        CASE WHEN tg_op = 'INSERT' THEN NEW.annotator_id 
                             WHEN OLD.annotator_id = NEW.annotator_id THEN NULL 
                             ELSE NEW.annotator_id 
                        END, 
                        CASE WHEN tg_op = 'INSERT' THEN NEW.geometry 
                             WHEN st_equals(OLD.geometry, NEW.geometry) THEN NULL 
                             ELSE NEW.geometry 
                        END,
                        CASE WHEN tg_op = 'INSERT' THEN NEW.taxonomy_class_id 
                             WHEN OLD.taxonomy_class_id = NEW.taxonomy_class_id THEN NULL 
                             ELSE NEW.taxonomy_class_id 
                        END,
                        CASE WHEN tg_op = 'INSERT' THEN NEW.image_name 
                             WHEN OLD.image_name = NEW.image_name THEN NULL 
                             ELSE NEW.image_name 
                        END,
                        CASE WHEN tg_op = 'INSERT' THEN NEW.status::annotation_status_enum
                             WHEN OLD.status = NEW.status THEN NULL 
                             ELSE NEW.status 
                        END,
                        CASE WHEN tg_op = 'INSERT' THEN NEW.review_requested
                             WHEN OLD.review_requested = NEW.review_requested THEN NULL 
                             ELSE NEW.review_requested 
                        END,
                        lower(tg_op)::annotation_log_operation_enum
                    );
                    RETURN NEW; 
                END;
            $$ LANGUAGE 'plpgsql';

            CREATE TRIGGER log_annotation_action AFTER INSERT OR UPDATE ON annotation
            FOR EACH ROW EXECUTE PROCEDURE annotation_save_event();
        """


def upgrade():
    # ---------
    # Add columns
    # ---------
    op.add_column(
        "annotation",
        sa.Column(
            "review_requested",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_annotation_review_requested"),
        "annotation",
        ["review_requested"],
        unique=False,
    )
    op.add_column(
        "annotation_log", sa.Column("review_requested", sa.Boolean(), nullable=True)
    )

    # ---------
    # Modify triggers
    # ---------
    op.execute("drop trigger if exists log_annotation_action on annotation cascade;")

    op.execute(trigger_annotation_save)


def downgrade():
    # ---------
    # Remove columns
    # ---------
    op.drop_column("annotation_log", "review_requested")
    op.drop_index(op.f("ix_annotation_review_requested"), table_name="annotation")
    op.drop_column("annotation", "review_requested")

    # ---------
    # Triggers
    # ---------

    op.execute("drop trigger if exists log_annotation_action on annotation cascade;")

    import sys

    sys.path.append(str(Path(__file__).parent))
    from fba33e3dbe70_03_indices_and_annotation_status import trigger_annotation_save

    op.execute(trigger_annotation_save)
