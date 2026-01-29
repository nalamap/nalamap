"""Add maps, layers, and map_layers tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20250310_add_maps_layers"
down_revision = "20250226_add_oidc_columns"
branch_labels = None
depends_on = None


def _has_table(conn, table_name: str) -> bool:
    inspector = sa.inspect(conn)
    return inspector.has_table(table_name)


def upgrade():
    conn = op.get_bind()
    if not _has_table(conn, "maps"):
        op.create_table(
            "maps",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("name", sa.TEXT(), nullable=False),
            sa.Column("description", sa.TEXT(), nullable=True),
        )

    if not _has_table(conn, "layers"):
        op.create_table(
            "layers",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("data_link", sa.TEXT(), nullable=False),
            sa.Column("data_type", sa.TEXT(), nullable=False),
            sa.Column("name", sa.TEXT(), nullable=False),
            sa.Column("description", sa.TEXT(), nullable=True),
            sa.Column("derived", sa.BOOLEAN(), nullable=False, server_default=sa.text("false")),
            sa.Column("style", postgresql.JSONB(), nullable=True),
        )

    if not _has_table(conn, "map_layers"):
        op.create_table(
            "map_layers",
            sa.Column(
                "map_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("maps.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "layer_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("layers.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("z_index", sa.INTEGER(), nullable=False, server_default=sa.text("0")),
            sa.Column("visible", sa.BOOLEAN(), nullable=False, server_default=sa.text("true")),
        )


def downgrade():
    conn = op.get_bind()
    if _has_table(conn, "map_layers"):
        op.drop_table("map_layers")
    if _has_table(conn, "layers"):
        op.drop_table("layers")
    if _has_table(conn, "maps"):
        op.drop_table("maps")
