"""Add OIDC identity columns and allow passwordless users."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250226_add_oidc_columns"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("oidc_provider", sa.TEXT(), nullable=True))
    op.add_column("users", sa.Column("oidc_subject", sa.TEXT(), nullable=True))
    op.create_unique_constraint(
        "uq_users_oidc_identity", "users", ["oidc_provider", "oidc_subject"]
    )
    op.alter_column("users", "password_hash", existing_type=sa.TEXT(), nullable=True)


def downgrade():
    op.alter_column("users", "password_hash", existing_type=sa.TEXT(), nullable=False)
    op.drop_constraint("uq_users_oidc_identity", "users", type_="unique")
    op.drop_column("users", "oidc_subject")
    op.drop_column("users", "oidc_provider")
