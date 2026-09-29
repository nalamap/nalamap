"""Tests for signed (SAS) blob URLs: never unsigned, user-delegation signing, key caching."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import services.storage.file_management as fm

BLOB_URL = "https://acct.blob.core.windows.net/uploads/f.json"
CONN = "DefaultEndpointsProtocol=https;AccountName=acct;AccountKey=dGVzdA=="
ACCOUNT_URL = "https://acct.blob.core.windows.net"


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(fm, "_delegation_cache", None)
    monkeypatch.setattr(fm, "AZ_CONTAINER", "uploads")
    monkeypatch.setattr(fm, "AZURE_SAS_EXPIRY_HOURS", 24)
    monkeypatch.setattr(fm, "AZURE_STORAGE_ACCOUNT_URL", "")
    monkeypatch.setattr(fm, "AZ_CONN", CONN)


def test_account_key_url_is_signed():
    url = fm._generate_sas_url(BLOB_URL, "f.json")
    assert url.startswith(BLOB_URL + "?")
    assert "sig=" in url and "sp=r" in url


@pytest.mark.parametrize("conn", ["", "AccountName=acct", "DefaultEndpointsProtocol=https"])
def test_missing_credentials_raise(monkeypatch, conn):
    monkeypatch.setattr(fm, "AZ_CONN", conn)
    with pytest.raises(fm.StorageSigningError):
        fm._generate_sas_url(BLOB_URL, "f.json")


def test_signing_exception_raises_without_leaking_secret(monkeypatch):
    with patch("azure.storage.blob.generate_blob_sas", side_effect=ValueError("dGVzdA==")):
        with pytest.raises(fm.StorageSigningError) as exc:
            fm._generate_sas_url(BLOB_URL, "f.json")
    assert "dGVzdA" not in str(exc.value)


def _delegation_mocks():
    key = MagicMock(name="delegation_key")
    svc = MagicMock()
    svc.get_user_delegation_key.return_value = key
    return key, svc


def test_user_delegation_used_when_account_url_set(monkeypatch):
    monkeypatch.setattr(fm, "AZURE_STORAGE_ACCOUNT_URL", ACCOUNT_URL)
    monkeypatch.setattr(fm, "AZ_CONN", "")
    key, svc = _delegation_mocks()
    with (
        patch("azure.identity.DefaultAzureCredential"),
        patch("azure.storage.blob.BlobServiceClient", return_value=svc),
        patch("azure.storage.blob.generate_blob_sas", return_value="sig=abc&sp=r") as gen,
    ):
        url = fm._generate_sas_url(BLOB_URL, "f.json")
    assert url == BLOB_URL + "?sig=abc&sp=r"
    kwargs = gen.call_args.kwargs
    assert kwargs["user_delegation_key"] is key
    assert kwargs["account_name"] == "acct"
    assert "account_key" not in kwargs
    assert kwargs["permission"].read and not kwargs["permission"].write
    start, expiry = svc.get_user_delegation_key.call_args.args
    assert expiry - start <= timedelta(days=7, minutes=5)
    assert kwargs["expiry"] <= expiry


def test_delegation_failure_falls_back_to_account_key(monkeypatch):
    monkeypatch.setattr(fm, "AZURE_STORAGE_ACCOUNT_URL", ACCOUNT_URL)
    svc = MagicMock()
    svc.get_user_delegation_key.side_effect = RuntimeError("no identity")
    with (
        patch("azure.identity.DefaultAzureCredential"),
        patch("azure.storage.blob.BlobServiceClient", return_value=svc),
    ):
        url = fm._generate_sas_url(BLOB_URL, "f.json")
    assert "sig=" in url


def test_delegation_and_key_both_fail_raises(monkeypatch):
    monkeypatch.setattr(fm, "AZURE_STORAGE_ACCOUNT_URL", ACCOUNT_URL)
    monkeypatch.setattr(fm, "AZ_CONN", "")
    svc = MagicMock()
    svc.get_user_delegation_key.side_effect = RuntimeError("no identity")
    with (
        patch("azure.identity.DefaultAzureCredential"),
        patch("azure.storage.blob.BlobServiceClient", return_value=svc),
    ):
        with pytest.raises(fm.StorageSigningError):
            fm._generate_sas_url(BLOB_URL, "f.json")


def test_delegation_key_cached_then_refreshed_at_half_life(monkeypatch):
    monkeypatch.setattr(fm, "AZURE_STORAGE_ACCOUNT_URL", ACCOUNT_URL)
    _, svc = _delegation_mocks()
    with (
        patch("azure.identity.DefaultAzureCredential"),
        patch("azure.storage.blob.BlobServiceClient", return_value=svc),
    ):
        fm._get_user_delegation_key()
        fm._get_user_delegation_key()
        assert svc.get_user_delegation_key.call_count == 1

        # Age the cached key past half-life
        key, start, expiry = fm._delegation_cache
        life = expiry - start
        aged = datetime.now(timezone.utc) - life * 0.6
        monkeypatch.setattr(fm, "_delegation_cache", (key, aged, aged + life))
        fm._get_user_delegation_key()
        assert svc.get_user_delegation_key.call_count == 2


def _azure_container():
    container = MagicMock()
    container.url = "https://acct.blob.core.windows.net/uploads"
    svc = MagicMock()
    svc.get_container_client.return_value = container
    svc.get_container_client.return_value.get_blob_client.return_value = MagicMock()
    return svc, container


def test_store_file_signed_url_and_no_unsigned_on_failure(monkeypatch):
    monkeypatch.setattr(fm, "USE_AZURE", True)
    svc, container = _azure_container()
    with patch("azure.storage.blob.BlobServiceClient") as cls:
        cls.from_connection_string.return_value = svc
        url, name = fm.store_file("a.json", b"{}")
        assert "sig=" in url

        monkeypatch.setattr(fm, "AZ_CONN", "AccountName=acct")
        cls.from_connection_string.return_value = svc
        with pytest.raises(fm.StorageSigningError):
            fm.store_file("a.json", b"{}")
    container.delete_blob.assert_called_once()


def test_store_file_stream_returns_503_and_cleans_up(monkeypatch):
    from io import BytesIO

    monkeypatch.setattr(fm, "USE_AZURE", True)
    monkeypatch.setattr(fm, "AZ_CONN", "AccountName=acct")
    svc, container = _azure_container()
    blob_client = container.get_blob_client.return_value
    with patch("azure.storage.blob.BlobServiceClient") as cls:
        cls.from_connection_string.return_value = svc
        with pytest.raises(HTTPException) as exc:
            fm.store_file_stream("a.json", BytesIO(b"{}"))
    assert exc.value.status_code == 503
    assert "AccountName" not in exc.value.detail
    blob_client.delete_blob.assert_called_once()
