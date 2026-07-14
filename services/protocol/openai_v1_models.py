from __future__ import annotations

from typing import Any

from services.openai_backend_api import OpenAIBackendAPI
from services.personal_account_service import personal_account_service
from utils.helper import CODEX_IMAGE_MODEL


_EXPOSED_MODELS = [
    "gpt-image-2",
    CODEX_IMAGE_MODEL,
    "auto",
    "gpt-5",
    "gpt-5-1",
    "gpt-5-2",
    "gpt-5-3",
    "gpt-5-3-mini",
    "gpt-5-mini",
]


def list_models() -> dict[str, Any]:
    backend = OpenAIBackendAPI()
    try:
        result = backend.list_models()
    finally:
        backend.close()
    data = result.get("data")
    if not isinstance(data, list):
        return result
    seen = {str(item.get("id") or "").strip() for item in data if isinstance(item, dict)}
    if personal_account_service.list_accounts():
        for model in _EXPOSED_MODELS:
            if model not in seen:
                data.append({
                    "id": model,
                    "object": "model",
                    "created": 0,
                    "owned_by": "chatgpt2api",
                    "permission": [],
                    "root": model,
                    "parent": None,
                })
    return result
