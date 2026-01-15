"""Add owner_id and payload fields to maps/layers."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20250310_add_owner_payload"
down_revision = "20250310_add_maps_layers"
branch_labels = None
depends_on = None


def _has_table(conn, table_name: str) -> bool:
    inspector = sa.inspect(conn)
    return inspector.has_table(table_name)


def _has_column(conn, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(conn)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_fk(conn, table_name: str, fk_name: str) -> bool:
    inspector = sa.inspect(conn)
    return any(fk.get("name") == fk_name for fk in inspector.get_foreign_keys(table_name))


def upgrade():
    conn = op.get_bind()

    if _has_table(conn, "maps"):
        if not _has_column(conn, "maps", "owner_id"):
            op.add_column("maps", sa.Column("owner_id", postgresql.UUID(as_uuid=True)))
        if not _has_fk(conn, "maps", "fk_maps_owner_id"):
            op.create_foreign_key(
                "fk_maps_owner_id",
                "maps",
                "users",
                ["owner_id"],
                ["id"],
                ondelete="CASCADE",
            )

    if _has_table(conn, "layers"):
        if not _has_column(conn, "layers", "owner_id"):
            op.add_column("layers", sa.Column("owner_id", postgresql.UUID(as_uuid=True)))
        if not _has_column(conn, "layers", "payload"):
            op.add_column("layers", sa.Column("payload", postgresql.JSONB()))
        if not _has_fk(conn, "layers", "fk_layers_owner_id"):
            op.create_foreign_key(
                "fk_layers_owner_id",
                "layers",
                "users",
                ["owner_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade():
    conn = op.get_bind()

    if _has_table(conn, "layers"):
        if _has_fk(conn, "layers", "fk_layers_owner_id"):
            op.drop_constraint("fk_layers_owner_id", "layers", type_="foreignkey")
        if _has_column(conn, "layers", "payload"):
            op.drop_column("layers", "payload")
        if _has_column(conn, "layers", "owner_id"):
            op.drop_column("layers", "owner_id")

    if _has_table(conn, "maps"):
        if _has_fk(conn, "maps", "fk_maps_owner_id"):
            op.drop_constraint("fk_maps_owner_id", "maps", type_="foreignkey")
        if _has_column(conn, "maps", "owner_id"):
            op.drop_column("maps", "owner_id")
