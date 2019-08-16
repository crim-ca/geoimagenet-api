"""14_dont_log_geometry_updates

Revision ID: d714ede8fd71
Revises: 66711f6c50e1
Create Date: 2019-08-16 14:52:40.337374

"""
from pathlib import Path

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision = 'd714ede8fd71'
down_revision = '66711f6c50e1'
branch_labels = None
depends_on = None


trigger_annotation_save = """
            CREATE OR REPLACE FUNCTION annotation_save_event() RETURNS trigger AS $$ 
                BEGIN 
                    -- If it's not a geometry update (which can happen way too often), log the action 
                    IF NOT (tg_op = 'UPDATE' AND NOT st_equals(OLD.geometry, NEW.geometry)) THEN
                        INSERT INTO annotation_log
                        (annotation_id, annotator_id, geometry, taxonomy_class_id, image_id, status, review_requested, operation)
                        VALUES (
                            NEW.id, 
                            CASE WHEN tg_op = 'INSERT' THEN NEW.annotator_id 
                                 WHEN OLD.annotator_id = NEW.annotator_id THEN NULL 
                                 ELSE NEW.annotator_id 
                            END, 
                            CASE WHEN tg_op = 'INSERT' THEN NEW.geometry 
                                 ELSE NULL
                            END,
                            CASE WHEN tg_op = 'INSERT' THEN NEW.taxonomy_class_id 
                                 WHEN OLD.taxonomy_class_id = NEW.taxonomy_class_id THEN NULL 
                                 ELSE NEW.taxonomy_class_id 
                            END,
                            CASE WHEN tg_op = 'INSERT' THEN NEW.image_id 
                                 WHEN OLD.image_id = NEW.image_id THEN NULL 
                                 ELSE NEW.image_id 
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
                    END IF;
                    NEW.updated_at = now();
                    RETURN NEW; 
                END;
            $$ LANGUAGE 'plpgsql';

            CREATE TRIGGER log_annotation_action AFTER INSERT OR UPDATE ON annotation
            FOR EACH ROW EXECUTE PROCEDURE annotation_save_event();
        """

def upgrade():
    op.alter_column('person', 'email', nullable=False)
    op.drop_constraint('person_username_key', 'person', type_='unique')

    # ---------
    # Triggers
    # ---------
    op.execute("drop trigger if exists log_annotation_action on annotation cascade;")
    op.execute(trigger_annotation_save)

def downgrade():
    op.create_unique_constraint('person_username_key', 'person', ['username'])
    op.alter_column('person', 'email', nullable=True)

    # ---------
    # Triggers
    # ---------
    op.execute("drop trigger if exists log_annotation_action on annotation cascade;")
    import sys

    sys.path.append(str(Path(__file__).parent))
    from a8fd058f13eb_11_create_image_table import (
        trigger_annotation_save as old_trigger_annotation,
    )

    op.execute(old_trigger_annotation)