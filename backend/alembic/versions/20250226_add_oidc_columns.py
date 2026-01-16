"""Add OIDC identity columns and allow passwordless users."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250226_add_oidc_columns"
down_revision = None
branch_labels = None
depends_on = None


def _has_column(conn, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(conn)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_unique_constraint(conn, table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(conn)
    constraints = inspector.get_unique_constraints(table_name)
    return any(constraint.get("name") == constraint_name for constraint in constraints)


def upgrade():
    conn = op.get_bind()
    if not _has_column(conn, "users", "oidc_provider"):
        op.add_column("users", sa.Column("oidc_provider", sa.TEXT(), nullable=True))
    if not _has_column(conn, "users", "oidc_subject"):
        op.add_column("users", sa.Column("oidc_subject", sa.TEXT(), nullable=True))
    if not _has_unique_constraint(conn, "users", "uq_users_oidc_identity"):
        op.create_unique_constraint(
            "uq_users_oidc_identity", "users", ["oidc_provider", "oidc_subject"]
        )
    if _has_column(conn, "users", "password_hash"):
        op.alter_column("users", "password_hash", existing_type=sa.TEXT(), nullable=True)


def downgrade():
    conn = op.get_bind()
    if _has_column(conn, "users", "password_hash"):
        op.alter_column("users", "password_hash", existing_type=sa.TEXT(), nullable=False)
    if _has_unique_constraint(conn, "users", "uq_users_oidc_identity"):
        op.drop_constraint("uq_users_oidc_identity", "users", type_="unique")
    if _has_column(conn, "users", "oidc_subject"):
        op.drop_column("users", "oidc_subject")
    if _has_column(conn, "users", "oidc_provider"):
        op.drop_column("users", "oidc_provider")
