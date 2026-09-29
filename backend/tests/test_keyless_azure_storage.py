"""End-to-end regression tests for keyless Azure Blob mode.

Only the account URL + container + USE_AZURE_STORAGE are configured (no connection string, no
account key); auth comes from a managed identity (DefaultAzureCredential). Clients are mocked.
"""

import asyncio
import importlib
import io
from unittest.mock import MagicMock, patch

import pytest

import services.storage.file_management as fm

ACCOUNT_URL = "https://acct.blob.core.windows.net"
CONTAINER_URL = f"{ACCOUNT_URL}/uploads"


@pytest.fixture(autouse=True)
def keyless(monkeypatch):
    monkeypatch.setattr(fm, "_delegation_cache", None)
    monkeypatch.setattr(fm, "USE_AZURE", True)
    monkeypatch.setattr(fm, "AZ_CONN", "")
    monkeypatch.setattr(fm, "AZ_CONTAINER", "uploads")
    monkeypatch.setattr(fm, "AZURE_STORAGE_ACCOUNT_URL", ACCOUNT_URL)
    monkeypatch.setattr(fm, "AZURE_SAS_EXPIRY_HOURS", 24)


@pytest.fixture
def svc():
    """Mocked BlobServiceClient patched in place of the real class (identity-based)."""
    service = MagicMock()
    container = service.get_container_client.return_value
    container.url = CONTAINER_URL
    service.get_user_delegation_key.return_value = "delegation-key"
    with (
        patch("azure.identity.DefaultAzureCredential") as cred,
        patch("azure.storage.blob.BlobServiceClient", return_value=service) as cls,
        patch("azure.storage.blob.generate_blob_sas", return_value="sig=abc") as sas,
    ):
        service.cls, service.cred, service.sas = cls, cred, sas
        yield service


def _assert_keyless(svc):
    svc.cls.from_connection_string.assert_not_called()
    svc.cls.assert_called_with(ACCOUNT_URL, credential=svc.cred.return_value)
    for call in svc.sas.call_args_list:
        assert call.kwargs["user_delegation_key"] == "delegation-key"
        assert "account_key" not in call.kwargs


def test_config_does_not_derive_use_azure_from_connection_string(monkeypatch):
    import core.config as cfg

    monkeypatch.setenv("USE_AZURE_STORAGE", "true")
    monkeypatch.setenv("AZURE_CONN_STRING", "")
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_URL", ACCOUNT_URL)
    try:
        importlib.reload(cfg)
        assert cfg.USE_AZURE is True
        assert cfg.AZ_CONN == ""
        assert cfg.AZURE_STORAGE_ACCOUNT_URL == ACCOUNT_URL
    finally:
        monkeypatch.undo()
        importlib.reload(cfg)


def test_store_file_uploads_and_signs_keyless(svc):
    url, name = fm.store_file("a.json", b"{}")
    container = svc.get_container_client.return_value
    container.upload_blob.assert_called_once()
    assert url == f"{CONTAINER_URL}/{name}?sig=abc"
    _assert_keyless(svc)


def test_store_file_compresses_large_geojson_keyless(svc):
    _, name = fm.store_file("big.geojson", b"x" * (fm.MIN_COMPRESS_SIZE + 1))
    kwargs = svc.get_container_client.return_value.upload_blob.call_args.kwargs
    assert kwargs["content_settings"].content_encoding == "gzip"
    assert len(kwargs["data"]) < fm.MIN_COMPRESS_SIZE
    _assert_keyless(svc)


def test_store_file_stream_keyless(svc):
    url, name = fm.store_file_stream("a.json", io.BytesIO(b"{}"))
    blob = svc.get_container_client.return_value.get_blob_client.return_value
    blob.upload_blob.assert_called_once()
    assert url == f"{CONTAINER_URL}/{name}?sig=abc"
    _assert_keyless(svc)


def test_store_file_stream_compresses_large_geojson_keyless(svc):
    fm.store_file_stream("big.geojson", io.BytesIO(b"x" * (fm.MIN_COMPRESS_SIZE + 1)))
    blob = svc.get_container_client.return_value.get_blob_client.return_value
    assert blob.upload_blob.call_args.kwargs["content_settings"].content_encoding == "gzip"
    _assert_keyless(svc)


def test_no_container_create_or_exists_call(svc):
    fm.store_file("a.json", b"{}")
    fm.store_file_stream("b.json", io.BytesIO(b"{}"))
    container = svc.get_container_client.return_value
    container.create_container.assert_not_called()
    container.exists.assert_not_called()
    svc.create_container.assert_not_called()


def test_sas_failure_never_returns_unsigned_url_and_cleans_up(svc):
    svc.get_user_delegation_key.side_effect = RuntimeError("secret-token-value")
    with pytest.raises(fm.StorageSigningError) as exc:
        fm.store_file("a.json", b"{}")
    assert "secret-token-value" not in str(exc.value)
    svc.get_container_client.return_value.delete_blob.assert_called_once()


def test_upload_meta_keyless(svc, monkeypatch):
    import api.data_management as dm

    monkeypatch.setattr(dm.core_config, "USE_AZURE", True)
    monkeypatch.setattr(dm.core_config, "AZ_CONN", "")
    monkeypatch.setattr(dm.core_config, "AZURE_STORAGE_ACCOUNT_URL", ACCOUNT_URL)
    monkeypatch.setattr(dm.core_config, "AZ_CONTAINER", "uploads")
    blob = svc.get_container_client.return_value.get_blob_client.return_value
    blob.download_blob.return_value.chunks.return_value = [b"ab", b"c"]
    out = asyncio.run(dm.get_upload_meta("f.json"))
    assert out["storage"] == "azure" and out["size"] == "3"
    svc.cls.from_connection_string.assert_not_called()
