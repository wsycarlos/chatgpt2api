import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from services.personal_account_service import PersonalAccountService
from services.protocol.conversation import ConversationRequest, ImageGenerationError, ImageOutput, _generate_single_image
from services.storage.json_storage import JSONStorageBackend


class FakeBackend:
    def __init__(self, access_token: str = "") -> None:
        self.access_token = access_token
        self.progress_callback = None


class TestImageAccountFailover(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.backend = JSONStorageBackend(self.tmpdir / "accounts.json")
        self.account_service = PersonalAccountService(self.backend)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_image_generation_failure_switches_active_account_and_retries(self):
        first = self.account_service.add_account({"access_token": "token-1", "email": "a@example.com"})
        second = self.account_service.add_account({"access_token": "token-2", "email": "b@example.com"})
        attempts = []

        def fake_stream(backend, request, index, total):
            attempts.append(backend.access_token)
            if backend.access_token == "token-1":
                raise RuntimeError("HTTP 429 rate limited")
            yield ImageOutput(kind="result", model=request.model, index=index, total=total, data=[{"url": "ok"}])

        with mock.patch("services.protocol.conversation.personal_account_service", self.account_service), \
                mock.patch("services.protocol.conversation.OpenAIBackendAPI", FakeBackend), \
                mock.patch("services.protocol.conversation.stream_image_outputs", fake_stream):
            outputs = _generate_single_image(ConversationRequest(model="gpt-image-2", prompt="x"), 1, 1)

        self.assertEqual([output.kind for output in outputs], ["result"])
        self.assertEqual(attempts, ["token-1", "token-2"])
        self.assertEqual(self.account_service.get_default_account()["id"], second["id"])
        self.assertNotEqual(self.account_service.get_default_account()["id"], first["id"])

    def test_image_generation_restores_first_active_account_when_all_accounts_fail(self):
        first = self.account_service.add_account({"access_token": "token-1", "email": "a@example.com"})
        self.account_service.add_account({"access_token": "token-2", "email": "b@example.com"})
        attempts = []

        def fake_stream(backend, request, index, total):
            attempts.append(backend.access_token)
            raise RuntimeError(f"failure on {backend.access_token}")
            yield

        with mock.patch("services.protocol.conversation.personal_account_service", self.account_service), \
                mock.patch("services.protocol.conversation.OpenAIBackendAPI", FakeBackend), \
                mock.patch("services.protocol.conversation.stream_image_outputs", fake_stream):
            with self.assertRaises(ImageGenerationError) as raised:
                _generate_single_image(ConversationRequest(model="gpt-image-2", prompt="x"), 1, 1)

        self.assertEqual(attempts, ["token-1", "token-2"])
        self.assertIn("failure on token-2", str(raised.exception))
        self.assertEqual(self.account_service.get_default_account()["id"], first["id"])

    def test_invalid_token_refresh_that_keeps_same_token_fails_over(self):
        first = self.account_service.add_account({"access_token": "token-1", "email": "a@example.com"})
        second = self.account_service.add_account({"access_token": "token-2", "email": "b@example.com"})
        attempts = []

        def fake_stream(backend, request, index, total):
            attempts.append(backend.access_token)
            if backend.access_token == "token-1":
                raise RuntimeError("token_invalidated")
            yield ImageOutput(kind="result", model=request.model, index=index, total=total, data=[{"url": "ok"}])

        with mock.patch("services.protocol.conversation.personal_account_service", self.account_service), \
                mock.patch.object(self.account_service, "refresh_access_token", return_value=first), \
                mock.patch("services.protocol.conversation.OpenAIBackendAPI", FakeBackend), \
                mock.patch("services.protocol.conversation.stream_image_outputs", fake_stream):
            outputs = _generate_single_image(ConversationRequest(model="gpt-image-2", prompt="x"), 1, 1)

        self.assertEqual([output.kind for output in outputs], ["result"])
        self.assertEqual(attempts, ["token-1", "token-2"])
        self.assertEqual(self.account_service.get_default_account()["id"], second["id"])

    def test_empty_output_from_connection_drop_fails_over(self):
        first = self.account_service.add_account({"access_token": "token-1", "email": "a@example.com"})
        second = self.account_service.add_account({"access_token": "token-2", "email": "b@example.com"})
        attempts = []

        def fake_stream(backend, request, index, total):
            attempts.append(backend.access_token)
            if backend.access_token == "token-1":
                return
                yield
            yield ImageOutput(kind="result", model=request.model, index=index, total=total, data=[{"url": "ok"}])

        with mock.patch("services.protocol.conversation.personal_account_service", self.account_service), \
                mock.patch("services.protocol.conversation.OpenAIBackendAPI", FakeBackend), \
                mock.patch("services.protocol.conversation.stream_image_outputs", fake_stream):
            outputs = _generate_single_image(ConversationRequest(model="gpt-image-2", prompt="x"), 1, 1)

        self.assertEqual([output.kind for output in outputs], ["result"])
        self.assertEqual(attempts, ["token-1", "token-2"])
        self.assertEqual(self.account_service.get_default_account()["id"], second["id"])


if __name__ == "__main__":
    unittest.main()
