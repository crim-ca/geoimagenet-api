"""03_indices_and_annotation_status

Revision ID: fba33e3dbe70
Revises: c83f405af323
Create Date: 2019-01-30 20:53:58.270863

"""
from pathlib import Path

from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
from sqlalchemy.dialects import postgresql

revision = "fba33e3dbe70"
down_revision = "c83f405af323"
branch_labels = None
depends_on = None

statuses = ("new", "released", "validated", "rejected", "deleted")

annotation_log_descriptions = ("insert", "update", "delete")


def upgrade():
    # ---------
    # Drop
    # ---------
    op.drop_column("annotation", "released")
    op.drop_column("annotation_log", "released")
    op.drop_column("annotation_log", "description")
    op.drop_table("annotation_log_description")
    # delete every annotation logs
    op.execute("truncate table annotation_log")
    # delete trigger that prevented updating a released annotation
    op.execute("drop trigger if exists annotation_update_check on annotation cascade;")

    # ---------
    # Create indices
    # ---------
    op.create_index(
        op.f("ix_annotation_annotator_id"), "annotation", ["annotator_id"], unique=False
    )
    op.create_index(
        op.f("ix_annotation_status"), "annotation", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_annotation_log_status"), "annotation_log", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_annotation_taxonomy_class_id"),
        "annotation",
        ["taxonomy_class_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_annotation_log_annotation_id"),
        "annotation_log",
        ["annotation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_annotation_log_annotator_id"),
        "annotation_log",
        ["annotator_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_annotation_log_taxonomy_class_id"),
        "annotation_log",
        ["taxonomy_class_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_taxonomy_class_name"), "taxonomy_class", ["name"], unique=False
    )
    op.create_index(
        op.f("ix_taxonomy_class_parent_id"),
        "taxonomy_class",
        ["parent_id"],
        unique=False,
    )

    # ---------
    # Create enums
    # ---------
    annotation_status_enum = postgresql.ENUM(*statuses, name="annotation_status_enum")
    annotation_status_enum.create(op.get_bind())

    annotation_log_operation_enum = postgresql.ENUM(
        *annotation_log_descriptions, name="annotation_log_operation_enum"
    )
    annotation_log_operation_enum.create(op.get_bind())

    # ---------
    # Add columns
    # ---------
    op.add_column(
        "annotation",
        sa.Column(
            "status",
            sa.Enum(*statuses, name="annotation_status_enum"),
            nullable=False,
            server_default="new",
        ),
    )
    op.add_column(
        "annotation_log",
        sa.Column("status", sa.Enum(*statuses, name="annotation_status_enum")),
    )
    op.add_column(
        "annotation_log",
        sa.Column(
            "operation",
            sa.Enum(*annotation_log_descriptions, name="annotation_log_operation_enum"),
            nullable=False,
        ),
    )

    # ---------
    # Modify triggers
    # ---------
    op.execute("drop trigger if exists log_annotation_action on annotation cascade;")

    trigger = """
            CREATE OR REPLACE FUNCTION annotation_save_event() RETURNS trigger AS $$ 
                BEGIN 
                    INSERT INTO annotation_log
                    (annotation_id, annotator_id, geometry, taxonomy_class_id, image_name, status, operation)
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
                        CASE WHEN tg_op = 'INSERT' THEN NEW.status 
                             WHEN OLD.status = NEW.status THEN NULL 
                             ELSE NEW.status 
                        END,
                        lower(tg_op)::annotation_log_operation_enum
                    );
                    RETURN NEW; 
                END;
            $$ LANGUAGE 'plpgsql';

            CREATE TRIGGER log_annotation_action AFTER INSERT OR UPDATE ON annotation
            FOR EACH ROW EXECUTE PROCEDURE annotation_save_event();
        """
    op.execute(trigger)

    op.execute(
        "drop trigger if exists log_annotation_action_delete on annotation cascade;"
    )

    trigger_delete = """
            CREATE OR REPLACE FUNCTION annotation_delete_event() RETURNS trigger AS $$ 
                BEGIN 
                    INSERT INTO annotation_log 
                        (
                            annotation_id, 
                            operation
                        ) 
                    VALUES (
                        OLD.id,
                        'delete'::annotation_log_operation_enum
                    );
                    RETURN NEW;
                END; 
            $$ LANGUAGE 'plpgsql';

            CREATE TRIGGER log_annotation_action_delete AFTER DELETE ON annotation
            FOR EACH ROW EXECUTE PROCEDURE annotation_delete_event();
        """
    op.execute(trigger_delete)


def downgrade():
    # ---------
    # Drop
    # ---------
    op.drop_index(op.f("ix_taxonomy_class_parent_id"), table_name="taxonomy_class")
    op.drop_index(op.f("ix_taxonomy_class_name"), table_name="taxonomy_class")
    op.drop_index(
        op.f("ix_annotation_log_taxonomy_class_id"), table_name="annotation_log"
    )
    op.drop_index(op.f("ix_annotation_log_annotator_id"), table_name="annotation_log")
    op.drop_index(op.f("ix_annotation_log_annotation_id"), table_name="annotation_log")
    op.drop_index(op.f("ix_annotation_taxonomy_class_id"), table_name="annotation")
    op.drop_index(op.f("ix_annotation_status"), table_name="annotation")
    op.drop_index(op.f("ix_annotation_annotator_id"), table_name="annotation")

    # drop columns
    op.drop_column("annotation", "status")
    op.drop_column("annotation_log", "status")
    op.drop_column("annotation_log", "operation")

    # drop enum type
    op.execute("DROP TYPE annotation_status_enum;")
    op.execute("DROP TYPE annotation_log_operation_enum;")

    # ---------
    # Add columns back
    # ---------
    op.add_column(
        "annotation",
        released=sa.Column(
            "released",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column("annotation_log", sa.Column("released", sa.BOOLEAN()))
    op.create_table(
        "annotation_log_description",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.add_column(
        "annotation_log",
        sa.Column("description", sa.Integer(), server_default="1", nullable=True),
    )

    # ---------
    # Triggers
    # ---------
    # Note: we don't bother adding the trigger that prevented a released annotation being updated

    op.execute("drop trigger if exists log_annotation_action on annotation cascade;")
    op.execute("drop trigger if exists log_annotation_action_delete on annotation cascade;")

    import sys

    sys.path.append(str(Path(__file__).parent))
    from c83f405af323_02_annotation_triggers import (
        trigger_annotation_save,
        trigger_delete,
    )

    op.execute(trigger_annotation_save)
    op.execute(trigger_delete)

