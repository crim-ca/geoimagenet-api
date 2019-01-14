"""02_annotation_triggers

Revision ID: c83f405af323
Revises: b1343731b6ab
Create Date: 2018-12-17 17:01:04.809382

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision = "c83f405af323"
down_revision = "cf75a8c51b24"
branch_labels = None
depends_on = None


def upgrade():
    trigger = """
        CREATE OR REPLACE FUNCTION annotation_save_event() RETURNS trigger AS $$ 
            BEGIN 
                INSERT INTO annotation_log
                (annotation_id, annotator_id, geometry, taxonomy_class_id, image_name, released, description)
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
                    CASE WHEN tg_op = 'INSERT' THEN NEW.released 
                         WHEN OLD.released = NEW.released THEN NULL 
                         ELSE NEW.released 
                    END,
                    (SELECT id FROM annotation_log_description WHERE name=lower(tg_op))
                );
                RETURN NEW; 
            END;
        $$ LANGUAGE 'plpgsql';

        CREATE TRIGGER log_annotation_action AFTER INSERT OR UPDATE ON annotation
        FOR EACH ROW EXECUTE PROCEDURE annotation_save_event();
    """
    op.execute(trigger)
    trigger_delete = """
        CREATE OR REPLACE FUNCTION annotation_delete_event() RETURNS trigger AS $$ 
            BEGIN 
                INSERT INTO annotation_log 
                    (
                        annotation_id, 
                        description
                    ) 
                SELECT 
                    OLD.id, 
                    annotation_log_description.id
                FROM annotation_log_description 
                WHERE name=lower(tg_op);
                RETURN NEW;
            END; 
        $$ LANGUAGE 'plpgsql';

        CREATE TRIGGER log_annotation_action_delete AFTER DELETE ON annotation
        FOR EACH ROW EXECUTE PROCEDURE annotation_delete_event();
    """
    op.execute(trigger_delete)

    trigger_annotation_update = """
        CREATE OR REPLACE FUNCTION annotation_update_check() 
        RETURNS trigger AS 
        $$ 
            BEGIN 
                IF OLD.released AND NEW.released THEN
                    RAISE EXCEPTION 'Can''t update an annotation that is ''released''.';
                END IF;
                NEW.updated_at = NOW();
                RETURN NEW; 
            END; 
        $$ LANGUAGE 'plpgsql';

        CREATE TRIGGER annotation_update_check BEFORE UPDATE
        ON annotation
        FOR EACH ROW EXECUTE PROCEDURE annotation_update_check();
    """

    op.execute(trigger_annotation_update)

    op.bulk_insert(
        anno_table, [{"name": "insert"}, {"name": "update"}, {"name": "delete"}]
    )


anno_table = table("annotation_log_description", column("name", sa.String))


def downgrade():
    op.execute("drop trigger if exists log_annotation_action on annotation cascade;")
    op.execute(
        "drop trigger if exists log_annotation_action_delete on annotation cascade;"
    )
    op.execute("drop trigger if exists annotation_update_check on annotation cascade;")
    op.execute(
        anno_table.delete().where(anno_table.c.name.in_(["insert", "update", "delete"]))
    )
