import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.openai_backend_api import ChatRequirements, OpenAIBackendAPI
from utils.conversation_patch import strip_history


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

    def test_resume_search_result_returns_only_final_assistant_message(self) -> None:
        response = FakeResponse([
            {
                "message": {
                    "id": "reasoning-1",
                    "author": {"role": "assistant"},
                    "channel": "analysis",
                    "content": {"content_type": "thought", "parts": ["Private reasoning"]},
                },
            },
            "malformed payload",
            {
                "unrelated": {
                    "message": {
                        "id": "nested-user-1",
                        "author": {"role": "assistant"},
                        "channel": "final",
                        "content": {"content_type": "text", "parts": ["Wrong answer"]},
                    },
                },
                "message": {
                    "id": "final-1",
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": ["Final answer https://example.com"]},
                    "metadata": {
                        "channel": "final",
                        "finish_details": {"type": "finished_successfully"},
                        "citations": [{"title": "Example", "url": "https://example.com"}],
                    },
                    "create_time": 123.0,
                },
            },
            "[DONE]",
        ])
        backend = OpenAIBackendAPI(access_token="token")
        backend.session.post = mock.Mock(return_value=response)

        result = backend._resume_search_result("conv-1", "resume-token")

        self.assertEqual(result, {
            "conversation_id": "conv-1",
            "status": "finished_successfully",
            "answer": "Final answer https://example.com",
            "sources": [{
                "title": "Example",
                "url": "https://example.com",
                "snippet": "",
                "source_type": "",
            }],
            "assistant_message_id": "final-1",
            "create_time": 123.0,
        })
        request = backend.session.post.call_args
        self.assertTrue(request.args[0].endswith("/backend-api/f/conversation/resume"))
        self.assertEqual(request.kwargs["json"], {"conversation_id": "conv-1", "offset": 0})
        self.assertEqual(request.kwargs["headers"]["X-Conduit-Token"], "resume-token")
        self.assertEqual(request.kwargs["timeout"], 300.0)
        self.assertTrue(response.closed)

    def test_resume_search_result_decodes_v1_final_message_patches(self) -> None:
        response = FakeResponse([
            "v1",
            {
                "p": "",
                "o": "add",
                "v": {"message": {
                    "id": "reasoning-1",
                    "author": {"role": "assistant"},
                    "channel": "analysis",
                    "content": {"content_type": "reasoning", "parts": [""]},
                    "status": "in_progress",
                }},
            },
            {"p": "/message/content/parts/0", "o": "append", "v": "Private reasoning"},
            {
                "p": "",
                "o": "add",
                "v": {"message": {
                    "id": "final-2",
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text", "parts": [""]},
                    "metadata": {
                        "channel": "final",
                        "citations": [{"title": "Example", "url": "https://example.com"}],
                    },
                    "status": "in_progress",
                    "create_time": 456.0,
                }},
            },
            {"p": "/message/content/parts/0", "o": "append", "v": "Final answer"},
            {"v": " https://example.com"},
            {"p": "", "o": "patch", "v": [
                {"p": "/message/content/parts/0", "o": "append", "v": "!"},
                {"p": "/message/status", "o": "replace", "v": "finished_successfully"},
                {"p": "/message/end_turn", "o": "replace", "v": True},
            ]},
            "[DONE]",
        ])
        backend = OpenAIBackendAPI(access_token="token")
        backend.session.post = mock.Mock(return_value=response)

        result = backend._resume_search_result("conv-1", "resume-token")

        self.assertEqual(result["answer"], "Final answer https://example.com!")
        self.assertNotIn("Private reasoning", result["answer"])
        self.assertEqual(result["status"], "finished_successfully")
        self.assertEqual(result["assistant_message_id"], "final-2")
        self.assertEqual(result["sources"][0]["url"], "https://example.com")
        self.assertTrue(response.closed)

    def test_resume_search_result_does_not_patch_prior_final_after_new_message(self) -> None:
        response = FakeResponse([
            {"message": {
                "id": "final-1",
                "author": {"role": "assistant"},
                "channel": "final",
                "content": {"content_type": "text", "parts": ["Good"]},
                "status": "finished_successfully",
            }},
            {"v": {"message": {
                "id": "reasoning-2",
                "author": {"role": "assistant"},
                "channel": "analysis",
                "content": {"content_type": "reasoning", "parts": [""]},
                "status": "in_progress",
            }}},
            {"p": "/message/content/parts/0", "o": "append", "v": " SECRET"},
            "[DONE]",
        ])
        backend = OpenAIBackendAPI(access_token="token")
        backend.session.post = mock.Mock(return_value=response)

        result = backend._resume_search_result("conv-1", "resume-token")

        self.assertEqual(result["answer"], "Good")

    def test_resume_search_result_invalidates_partial_result_on_handoff(self) -> None:
        response = FakeResponse([
            {"message": {
                "id": "final-partial",
                "author": {"role": "assistant"},
                "channel": "final",
                "content": {"content_type": "text", "parts": ["Partial answer"]},
                "status": "finished_partial_completion",
            }},
            {"type": "stream_handoff", "conversation_id": "conv-1"},
            "[DONE]",
        ])
        backend = OpenAIBackendAPI(access_token="token")
        backend.session.post = mock.Mock(return_value=response)

        result = backend._resume_search_result("conv-1", "resume-token")

        self.assertFalse(result.get("answer"))

    def test_strip_history_keeps_default_history_argument(self) -> None:
        self.assertEqual(strip_history("answer"), "answer")


if __name__ == "__main__":
    unittest.main()
