from __future__ import annotations

import base64
import json
import time
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from curl_cffi import requests

from services.config import config
from services.openai_auth_constants import (
    auth_base,
    platform_base,
    platform_oauth_client_id,
    platform_oauth_redirect_uri,
    platform_auth0_client,
    user_agent,
)
from services.storage.base import StorageBackend

ACCESS_TOKEN_REFRESH_SKEW_SECONDS = 24 * 60 * 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_jwt_payload(token: str) -> dict:
    try:
        payload = str(token or "").split(".")[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _jwt_exp(token: str) -> int:
    try:
        return int(_decode_jwt_payload(token).get("exp") or 0)
    except Exception:
        return 0


def _token_expires_in(token: str) -> int | None:
    exp = _jwt_exp(token)
    if exp <= 0:
        return None
    return exp - int(time.time())


def _token_needs_refresh(token: str) -> bool:
    remaining = _token_expires_in(token)
    return remaining is not None and remaining <= ACCESS_TOKEN_REFRESH_SKEW_SECONDS


class PersonalAccountService:
    _OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"

    def __init__(self, storage: StorageBackend):
        self.storage = storage
        self._lock = Lock()
        self._accounts: list[dict[str, Any]] = self._load()

    def _load(self) -> list[dict[str, Any]]:
        items = self.storage.load_personal_accounts()
        if not isinstance(items, list):
            return []
        return [normalized for item in items if (normalized := self._normalize(item)) is not None]

    def _save(self) -> None:
        self.storage.save_personal_accounts(self._accounts)

    @staticmethod
    def _normalize(item: object) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        access_token = str(item.get("access_token") or "").strip()
        if not access_token:
            return None
        id_token = str(item.get("id_token") or "").strip() or None
        id_claims = _decode_jwt_payload(id_token or "")
        access_claims = _decode_jwt_payload(access_token)
        auth_claims = access_claims.get("https://api.openai.com/auth")
        auth_claims = auth_claims if isinstance(auth_claims, dict) else {}
        email = str(item.get("email") or id_claims.get("email") or "").strip() or None
        account_id = str(item.get("account_id") or auth_claims.get("chatgpt_account_id") or "").strip() or None
        account_type = str(item.get("type") or auth_claims.get("chatgpt_plan_type") or "").strip() or None
        return {
            "id": str(item.get("id") or uuid.uuid4().hex[:12]),
            "email": email,
            "account_id": account_id,
            "type": account_type,
            "access_token": access_token,
            "refresh_token": str(item.get("refresh_token") or "").strip() or None,
            "id_token": id_token,
            "is_default": bool(item.get("is_default", False)),
            "created_at": str(item.get("created_at") or _now_iso()),
            "updated_at": str(item.get("updated_at") or _now_iso()),
            "last_refresh_error": str(item.get("last_refresh_error") or "").strip() or None,
        }

    def list_accounts(self) -> list[dict[str, Any]]:
        with self._lock:
            self._accounts = self._load()
            return [dict(account) for account in self._accounts]

    def get_account(self, account_id: str) -> dict[str, Any] | None:
        with self._lock:
            for account in self._accounts:
                if account.get("id") == account_id:
                    return dict(account)
        return None

    def get_default_account(self) -> dict[str, Any] | None:
        accounts = self.list_accounts()
        if not accounts:
            return None
        for account in accounts:
            if account.get("is_default"):
                return dict(account)
        return dict(accounts[0])

    def switch_active_account(self, current_account_id: str) -> dict[str, Any] | None:
        with self._lock:
            if not self._accounts:
                return None
            current_index = next(
                (index for index, account in enumerate(self._accounts) if account.get("id") == current_account_id),
                -1,
            )
            next_index = (current_index + 1) % len(self._accounts) if current_index >= 0 else 0
            for index, account in enumerate(self._accounts):
                account["is_default"] = index == next_index
            self._save()
            return dict(self._accounts[next_index])

    def restore_active_account(self, account_id: str) -> dict[str, Any] | None:
        return self.set_default(account_id)

    def set_default(self, account_id: str) -> dict[str, Any] | None:
        with self._lock:
            found = None
            for account in self._accounts:
                if account.get("id") == account_id:
                    found = account
                    account["is_default"] = True
                else:
                    account["is_default"] = False
            if found is None:
                return None
            self._save()
            return dict(found)

    def add_account(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            normalized = self._normalize(payload)
            if normalized is None:
                raise ValueError("invalid account payload")
            existing_ids = {account["id"] for account in self._accounts}
            for index, account in enumerate(self._accounts):
                if account["access_token"] == normalized["access_token"]:
                    normalized["id"] = account["id"]
                    normalized["created_at"] = account["created_at"]
                    self._accounts[index] = normalized
                    if len(self._accounts) == 1:
                        self._accounts[0]["is_default"] = True
                    self._save()
                    return dict(normalized)
            while normalized["id"] in existing_ids:
                normalized["id"] = uuid.uuid4().hex[:12]
            if not self._accounts:
                normalized["is_default"] = True
            self._accounts.append(normalized)
            self._save()
            return dict(normalized)

    def delete_account(self, account_id: str) -> bool:
        with self._lock:
            before = len(self._accounts)
            self._accounts = [account for account in self._accounts if account.get("id") != account_id]
            if len(self._accounts) == before:
                return False
            if self._accounts and not any(account.get("is_default") for account in self._accounts):
                self._accounts[0]["is_default"] = True
            self._save()
            return True

    def refresh_access_token(self, account_id: str) -> dict[str, Any] | None:
        account = self.get_account(account_id)
        if account is None:
            return None
        access_token = account["access_token"]
        refresh_token = account.get("refresh_token") or ""
        if not refresh_token or not _token_needs_refresh(access_token):
            return account

        session = requests.Session(impersonate="chrome110", verify=False)
        try:
            response = session.post(
                self._OAUTH_TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": user_agent,
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": platform_oauth_client_id,
                },
                timeout=60,
            )
            data = response.json() if response.text else {}
            if response.status_code != 200 or not isinstance(data, dict) or not data.get("access_token"):
                raise RuntimeError(f"oauth_refresh_http_{response.status_code}")

            new_access_token = str(data.get("access_token") or "").strip()
            new_refresh_token = str(data.get("refresh_token") or refresh_token).strip()
            if not new_access_token:
                raise RuntimeError("empty access_token")

            with self._lock:
                for index, acc in enumerate(self._accounts):
                    if acc.get("id") == account_id:
                        self._accounts[index] = self._normalize({
                            **acc,
                            "access_token": new_access_token,
                            "refresh_token": new_refresh_token,
                            "id_token": str(data.get("id_token") or acc.get("id_token") or "").strip() or None,
                            "updated_at": _now_iso(),
                            "last_refresh_error": None,
                        })
                        self._save()
                        return dict(self._accounts[index])
            return None
        except Exception as exc:
            with self._lock:
                for index, acc in enumerate(self._accounts):
                    if acc.get("id") == account_id:
                        self._accounts[index]["last_refresh_error"] = str(exc)
                        self._accounts[index]["updated_at"] = _now_iso()
                        self._save()
                        break
            return None
        finally:
            session.close()

    def get_active_access_token(self) -> str:
        account = self.get_default_account()
        if account is None:
            return ""
        refreshed = self.refresh_access_token(account["id"])
        account = refreshed or account
        return str(account.get("access_token") or "")


personal_account_service = PersonalAccountService(config.get_storage_backend())
