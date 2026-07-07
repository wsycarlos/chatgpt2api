import unittest
from unittest import mock

from services.openai_backend_api import ChatRequirements, OpenAIBackendAPI


class _FakeResponse:
    def __init__(self) -> None:
        self.status_code = 200
        self.text = ""

    def json(self):
        return {}


class TestImageRoutingMode(unittest.TestCase):
    def test_image_generation_uses_balanced_parallel_switch(self):
        backend = OpenAIBackendAPI(access_token="token")
        captured_payloads = []

        def fake_post(url, **kwargs):
            captured_payloads.append(kwargs.get("json") or {})
            return _FakeResponse()

        with mock.patch.object(backend.session, "post", side_effect=fake_post):
            backend._start_image_generation(
                "draw a cat",
                ChatRequirements(token="requirements-token"),
                "conduit-token",
                "gpt-image-2",
            )

        self.assertEqual(captured_payloads[0]["force_parallel_switch"], "balanced")


if __name__ == "__main__":
    unittest.main()
