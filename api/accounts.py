from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from services.auth_service import auth_service
from services.oauth_login_service import OAuthLoginError, oauth_login_service
from services.personal_account_service import personal_account_service
from api.support import require_admin


class UserKeyCreateRequest(BaseModel):
    name: str = ""


class UserKeyUpdateRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    key: str | None = None


class AccountCreateRequest(BaseModel):
    tokens: list[str] = Field(default_factory=list)
    accounts: list[dict[str, Any]] = Field(default_factory=list)


class AccountDeleteRequest(BaseModel):
    ids: list[str] = Field(default_factory=list)


class AccountDefaultRequest(BaseModel):
    id: str = ""


class OAuthLoginStartRequest(BaseModel):
    email_hint: str = ""


class OAuthLoginFinishRequest(BaseModel):
    session_id: str = ""
    callback: str = ""


def _account_payload_token(item: dict[str, Any]) -> str:
    return str(item.get("access_token") or item.get("accessToken") or "").strip()


def _unique_tokens(tokens: list[str]) -> list[str]:
    return list(dict.fromkeys(str(token or "").strip() for token in tokens if str(token or "").strip()))


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/auth/users")
    async def list_user_keys(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"items": auth_service.list_keys(role="user")}

    @router.post("/api/auth/users")
    async def create_user_key(body: UserKeyCreateRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            item, raw_key = auth_service.create_key(role="user", name=body.name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
        return {"item": item, "key": raw_key, "items": auth_service.list_keys(role="user")}

    @router.post("/api/auth/users/{key_id}")
    async def update_user_key(
            key_id: str,
            body: UserKeyUpdateRequest,
            authorization: str | None = Header(default=None),
    ):
        require_admin(authorization)
        updates = {
            key: value
            for key, value in {
                "name": body.name,
                "enabled": body.enabled,
                "key": body.key,
            }.items()
            if value is not None
        }
        if not updates:
            raise HTTPException(status_code=400, detail={"error": "还没有检测到改动，请修改后再保存"})
        try:
            item = auth_service.update_key(key_id, updates, role="user")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
        if item is None:
            raise HTTPException(status_code=404, detail={"error": "这条用户密钥不存在，可能已经被删除"})
        return {"item": item, "items": auth_service.list_keys(role="user")}

    @router.delete("/api/auth/users/{key_id}")
    async def delete_user_key(key_id: str, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        if not auth_service.delete_key(key_id, role="user"):
            raise HTTPException(status_code=404, detail={"error": "这条用户密钥不存在，可能已经被删除"})
        return {"items": auth_service.list_keys(role="user")}

    @router.get("/api/accounts")
    async def get_accounts(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"items": personal_account_service.list_accounts()}

    @router.post("/api/accounts")
    async def create_accounts(body: AccountCreateRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        account_payloads = [item for item in body.accounts if isinstance(item, dict)]
        payload_tokens = [_account_payload_token(item) for item in account_payloads]
        tokens = _unique_tokens([*body.tokens, *payload_tokens])

        added: list[dict[str, Any]] = []
        skipped = 0
        for payload in account_payloads:
            try:
                added.append(personal_account_service.add_account(payload))
            except ValueError:
                skipped += 1
        for token in tokens:
            if not token:
                continue
            if any(item.get("access_token") == token for item in account_payloads):
                continue
            try:
                added.append(personal_account_service.add_account({"access_token": token}))
            except ValueError:
                skipped += 1

        return {"added": len(added), "skipped": skipped, "items": personal_account_service.list_accounts()}

    @router.delete("/api/accounts")
    async def delete_accounts(body: AccountDeleteRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        ids = [str(account_id or "").strip() for account_id in body.ids if str(account_id or "").strip()]
        if not ids:
            raise HTTPException(status_code=400, detail={"error": "ids is required"})
        deleted = 0
        for account_id in ids:
            if personal_account_service.delete_account(account_id):
                deleted += 1
        return {"deleted": deleted, "items": personal_account_service.list_accounts()}

    @router.post("/api/accounts/default")
    async def set_default_account(body: AccountDefaultRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        account_id = str(body.id or "").strip()
        if not account_id:
            raise HTTPException(status_code=400, detail={"error": "id is required"})
        account = personal_account_service.set_default(account_id)
        if account is None:
            raise HTTPException(status_code=404, detail={"error": "account not found"})
        return {"item": account, "items": personal_account_service.list_accounts()}

    @router.post("/api/accounts/oauth/start")
    async def start_oauth_login(
            body: OAuthLoginStartRequest,
            authorization: str | None = Header(default=None),
    ):
        require_admin(authorization)
        try:
            return await run_in_threadpool(oauth_login_service.start, body.email_hint)
        except OAuthLoginError as exc:
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    @router.post("/api/accounts/oauth/finish")
    async def finish_oauth_login(
            body: OAuthLoginFinishRequest,
            authorization: str | None = Header(default=None),
    ):
        require_admin(authorization)
        cb_preview = (body.callback or "")[:80]
        sid_preview = (body.session_id or "")[:8]
        print(
            f"[oauth-login] finish called: session_id={sid_preview}..., callback_preview={cb_preview!r}",
            flush=True,
        )
        try:
            tokens = await run_in_threadpool(oauth_login_service.finish, body.session_id, body.callback)
        except OAuthLoginError as exc:
            print(f"[oauth-login] finish rejected: {exc}", flush=True)
            raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

        payload = {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "id_token": tokens["id_token"],
            "source_type": "oauth_login",
        }
        account = personal_account_service.add_account(payload)
        return {"item": account, "items": personal_account_service.list_accounts()}

    return router
