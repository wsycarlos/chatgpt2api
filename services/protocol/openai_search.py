from __future__ import annotations

from services.openai_backend_api import OpenAIBackendAPI, SEARCH_MODEL
from services.personal_account_service import personal_account_service

MODEL = SEARCH_MODEL


def handle(body: dict[str, object]) -> dict[str, object]:
    account = personal_account_service.get_default_account()
    if account is None:
        raise RuntimeError("No ChatGPT account configured")
    token = account["access_token"]
    result = OpenAIBackendAPI(token).search(str(body["prompt"]))
    result["_account_email"] = str(account.get("email") or "")
    return result
