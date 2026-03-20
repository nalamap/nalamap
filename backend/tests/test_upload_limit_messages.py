import json
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

# Ensure backend package is importable
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import core.config as core_config
import main
from services.storage.file_management import store_file_stream


def test_store_file_stream_uses_configured_limit_in_413_detail(monkeypatch):
    import io

    with pytest.raises(HTTPException) as exc_info:
        monkeypatch.setattr(core_config, "MAX_FILE_SIZE", 5, raising=False)
        store_file_stream("big.bin", io.BytesIO(b"0123456789"))

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "File size exceeds the limit of 5 B."


@pytest.mark.asyncio
async def test_request_entity_too_large_handler_uses_configured_limit(monkeypatch):
    monkeypatch.setattr(main.core_config, "MAX_FILE_SIZE", 5, raising=False)

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/upload",
            "headers": [],
        }
    )

    response = await main.request_entity_too_large_handler(request, Exception())
    payload = json.loads(response.body)

    assert response.status_code == 413
    assert payload["detail"] == "File size exceeds the limit of 5 B. Please upload a smaller file."
