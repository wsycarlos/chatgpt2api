import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.openai_backend_api import ChatRequirements, OpenAIBackendAPI


class FakeResponse:
    def __init__(self, payloads: list[object]) -> None:
        self.lines = [
            f"data: {payload if payload == '[DONE]' else json.dumps(payload)}".encode()
            for payload in payloads
        ]
        self.closed = False
        self.status_code = 200

    def iter_lines(self):
        return iter(self.lines)

    def close(self) -> None:
        self.closed = True


class SearchHandoffTests(unittest.TestCase):
    def test_run_search_conversation_captures_handoff_metadata(self) -> None:
        response = FakeResponse([
            {
                "type": "resume_conversation_token",
                "token": "resume-token",
                "conversation_id": "conv-1",
            },
            {"type": "stream_handoff", "conversation_id": "conv-1"},
            "[DONE]",
            {
                "type": "resume_conversation_token",
                "token": "poison-token",
                "conversation_id": "conv-2",
            },
        ])
        backend = OpenAIBackendAPI(access_token="token")
        backend.session.post = mock.Mock(return_value=response)
        backend._get_chat_requirements = mock.Mock(return_value=ChatRequirements(token="requirements-token"))

        state = backend._run_search_conversation("prompt", "conduit-token", "model")

        self.assertEqual(state.conversation_id, "conv-1")
        self.assertEqual(state.resume_token, "resume-token")
        self.assertTrue(state.handoff)
        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
