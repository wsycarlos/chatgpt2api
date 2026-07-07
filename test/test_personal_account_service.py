import shutil
import tempfile
import unittest
import base64
import json
from pathlib import Path
from unittest import mock

from services.personal_account_service import PersonalAccountService
from services.storage.json_storage import JSONStorageBackend


def jwt_token(payload: dict) -> str:
    def encode(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode(payload)}.sig"


class TestPersonalAccountService(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.backend = JSONStorageBackend(self.tmpdir / "accounts.json")
        self.service = PersonalAccountService(self.backend)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_and_get_default(self):
        account = self.service.add_account({
            "access_token": "test-token-1",
            "refresh_token": "refresh-1",
            "email": "a@example.com",
        })
        self.assertTrue(account["is_default"])
        self.assertEqual(self.service.get_default_account()["email"], "a@example.com")

    def test_default_falls_back_to_first(self):
        self.service.add_account({"access_token": "t1"})
        a2 = self.service.add_account({"access_token": "t2"})
        self.service.set_default(a2["id"])
        self.assertEqual(self.service.get_default_account()["access_token"], "t2")

    def test_delete_resets_default(self):
        self.service.add_account({"access_token": "t1"})
        a2 = self.service.add_account({"access_token": "t2"})
        self.service.set_default(a2["id"])
        self.service.delete_account(a2["id"])
        self.assertEqual(self.service.get_default_account()["access_token"], "t1")

    def test_add_updates_existing_token(self):
        self.service.add_account({"access_token": "t1", "refresh_token": "r1"})
        self.service.add_account({"access_token": "t1", "refresh_token": "r2"})
        accounts = self.service.list_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["refresh_token"], "r2")

    def test_add_account_derives_email_from_id_token(self):
        id_token = jwt_token({"email": "person@example.com"})

        account = self.service.add_account({"access_token": "t1", "id_token": id_token})

        self.assertEqual(account["email"], "person@example.com")

    def test_add_account_stores_chatgpt_auth_claims_from_access_token(self):
        access_token = jwt_token({
            "https://api.openai.com/auth": {
                "chatgpt_account_id": "acc-123",
                "chatgpt_plan_type": "plus",
            }
        })

        account = self.service.add_account({"access_token": access_token})

        self.assertEqual(account["account_id"], "acc-123")
        self.assertEqual(account["type"], "plus")

    def test_get_active_access_token_with_no_account(self):
        self.assertEqual(self.service.get_active_access_token(), "")

    def test_switch_active_account_moves_to_next_account(self):
        first = self.service.add_account({"access_token": "t1", "email": "a@example.com"})
        second = self.service.add_account({"access_token": "t2", "email": "b@example.com"})

        active = self.service.switch_active_account(first["id"])

        self.assertEqual(active["id"], second["id"])
        self.assertEqual(self.service.get_default_account()["id"], second["id"])

    def test_switch_active_account_wraps_to_first_account(self):
        first = self.service.add_account({"access_token": "t1", "email": "a@example.com"})
        second = self.service.add_account({"access_token": "t2", "email": "b@example.com"})
        self.service.set_default(second["id"])

        active = self.service.switch_active_account(second["id"])

        self.assertEqual(active["id"], first["id"])
        self.assertEqual(self.service.get_default_account()["id"], first["id"])

    def test_restore_active_account_switches_back_to_first_attempt(self):
        first = self.service.add_account({"access_token": "t1", "email": "a@example.com"})
        second = self.service.add_account({"access_token": "t2", "email": "b@example.com"})
        self.service.set_default(second["id"])

        restored = self.service.restore_active_account(first["id"])

        self.assertEqual(restored["id"], first["id"])
        self.assertEqual(self.service.get_default_account()["id"], first["id"])

    @mock.patch("services.personal_account_service.requests.Session")
    def test_refresh_access_token(self, mock_session_cls):
        account = self.service.add_account({
            "access_token": "old-token",
            "refresh_token": "refresh-token",
            "id": "acc-1",
        })
        # Make token appear expired
        with mock.patch(
            "services.personal_account_service._token_needs_refresh", return_value=True
        ):
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.text = '{"access_token":"new-token","refresh_token":"new-refresh"}'
            mock_response.json.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh",
            }
            mock_session_cls.return_value.__enter__ = mock.Mock(return_value=mock_session_cls.return_value)
            mock_session_cls.return_value.__exit__ = mock.Mock(return_value=False)
            mock_session_cls.return_value.post.return_value = mock_response

            refreshed = self.service.refresh_access_token(account["id"])
            self.assertEqual(refreshed["access_token"], "new-token")
            self.assertEqual(refreshed["refresh_token"], "new-refresh")

    def test_persistence(self):
        self.service.add_account({"access_token": "t1", "email": "a@example.com"})
        service2 = PersonalAccountService(self.backend)
        accounts = service2.list_accounts()
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["email"], "a@example.com")


if __name__ == "__main__":
    unittest.main()
