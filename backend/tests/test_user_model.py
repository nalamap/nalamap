"""Tests for the User ORM model definition."""

import pytest

from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TEXT, TIMESTAMP

from db.models.user import User


@pytest.mark.unit
def test_user_model_columns():
    """Verify the User ORM model columns and their properties."""
    # Ensure correct table name
    assert User.__tablename__ == "users"

    columns = {col.name: col for col in User.__table__.columns}

    # id column: UUID primary key with gen_random_uuid default
    assert "id" in columns
    id_col = columns["id"]
    assert isinstance(id_col.type, PG_UUID)
    assert id_col.primary_key
    assert id_col.server_default is not None
    assert id_col.server_default.arg.text == "gen_random_uuid()"

    # email column: TEXT unique, not nullable
    assert "email" in columns
    email_col = columns["email"]
    assert isinstance(email_col.type, TEXT)
    assert not email_col.nullable
    assert email_col.unique

    # display_name column: TEXT, nullable
    assert "display_name" in columns
    display_col = columns["display_name"]
    assert isinstance(display_col.type, TEXT)
    assert display_col.nullable

    # created_at column: TIMESTAMP with timezone, default now()
    assert "created_at" in columns
    created_col = columns["created_at"]
    assert isinstance(created_col.type, TIMESTAMP)
    assert created_col.type.timezone
    assert created_col.server_default.arg.text.lower() == "now()"

    # password_hash column: stored bcrypt hash
    assert "password_hash" in columns
    pwd_col = columns["password_hash"]
    assert isinstance(pwd_col.type, TEXT)
    assert not pwd_col.nullable
