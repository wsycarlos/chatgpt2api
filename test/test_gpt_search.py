import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.openai_backend_api import ChatRequirements, OpenAIBackendAPI, SearchConversationState
from utils.conversation_patch import strip_history
from utils.helper import UpstreamHTTPError


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
    def _search_backend(self, state: SearchConversationState) -> OpenAIBackendAPI:
        backend = OpenAIBackendAPI(access_token="token")
        backend._prepare_search_conversation = mock.Mock(return_value="conduit-token")
        backend._bootstrap = mock.Mock()
        backend._run_search_conversation = mock.Mock(return_value=state)
        backend._resume_search_result = mock.Mock()
        backend._wait_search_result = mock.Mock(return_value={"answer": "polled"})
        return backend

    def test_search_handoff_without_resume_token_polls_with_custom_timing(self) -> None:
        backend = self._search_backend(SearchConversationState("conv-1", handoff=True))

        result = backend.search("prompt", timeout_secs=17.5, poll_interval_secs=0.25)

        self.assertEqual(result, {"answer": "polled"})
        backend._resume_search_result.assert_not_called()
        backend._wait_search_result.assert_called_once_with("conv-1", 17.5, 0.25)

    def test_search_empty_resume_result_falls_back_to_polling(self) -> None:
        backend = self._search_backend(SearchConversationState("conv-1", "resume-token", True))
        backend._resume_search_result.return_value = {}

        with mock.patch("services.openai_backend_api.time.monotonic", side_effect=[100.0, 125.0]):
            result = backend.search("prompt")

        self.assertEqual(result, {"answer": "polled"})
        backend._wait_search_result.assert_called_once_with("conv-1", 275.0, 3.0)

    def test_search_returns_nonempty_resumed_answer_without_polling(self) -> None:
        backend = self._search_backend(SearchConversationState("conv-1", "resume-token", True))
        resumed = {"answer": "resumed"}
        backend._resume_search_result.return_value = resumed

        result = backend.search("prompt", timeout_secs=19.0)

        self.assertIs(result, resumed)
        backend._resume_search_result.assert_called_once_with("conv-1", "resume-token", 19.0)
        backend._wait_search_result.assert_not_called()

    def test_search_nonpositive_timeout_skips_resume_and_polls_with_zero(self) -> None:
        for timeout_secs in (0, -1.0):
            with self.subTest(timeout_secs=timeout_secs):
                backend = self._search_backend(SearchConversationState("conv-1", "resume-token", True))

                result = backend.search("prompt", timeout_secs=timeout_secs, poll_interval_secs=0.5)

                self.assertEqual(result, {"answer": "polled"})
                backend._resume_search_result.assert_not_called()
                backend._wait_search_result.assert_called_once_with("conv-1", 0, 0.5)

    def test_search_transient_resume_errors_fall_back_to_polling(self) -> None:
        for status_code in (404, 409, 423, 429, 500, 502, 503, 504):
            with self.subTest(status_code=status_code):
                backend = self._search_backend(SearchConversationState("conv-1", "resume-token", True))
                backend._resume_search_result.side_effect = UpstreamHTTPError("resume", status_code, "retry")

                with mock.patch("services.openai_backend_api.time.monotonic", side_effect=[100.0, 125.0]):
                    result = backend.search("prompt")

                self.assertEqual(result, {"answer": "polled"})
                backend._wait_search_result.assert_called_once_with("conv-1", 275.0, 3.0)

    def test_search_resume_transport_error_falls_back_with_remaining_timeout(self) -> None:
        backend = self._search_backend(SearchConversationState("conv-1", "resume-token", True))
        backend._resume_search_result.side_effect = requests.RequestsError("connection reset")

        with mock.patch("services.openai_backend_api.time.monotonic", side_effect=[50.0, 70.0]):
            result = backend.search("prompt", timeout_secs=15.0, poll_interval_secs=0.5)

        self.assertEqual(result, {"answer": "polled"})
        backend._wait_search_result.assert_called_once_with("conv-1", 0, 0.5)

    def test_search_nontransient_resume_error_propagates_without_polling(self) -> None:
        backend = self._search_backend(SearchConversationState("conv-1", "resume-token", True))
        error = UpstreamHTTPError("resume", 400, "bad request")
        backend._resume_search_result.side_effect = error

        with self.assertRaises(UpstreamHTTPError) as raised:
            backend.search("prompt")

        self.assertIs(raised.exception, error)
        backend._wait_search_result.assert_not_called()

    def test_search_resume_runtime_error_propagates_without_polling(self) -> None:
        backend = self._search_backend(SearchConversationState("conv-1", "resume-token", True))
        error = RuntimeError("programming error")
        backend._resume_search_result.side_effect = error

        with self.assertRaises(RuntimeError) as raised:
            backend.search("prompt")

        self.assertIs(raised.exception, error)
        backend._wait_search_result.assert_not_called()

    def test_search_without_handoff_does_not_resume_even_with_token(self) -> None:
        backend = self._search_backend(SearchConversationState("conv-1", "resume-token", False))

        result = backend.search("prompt")

        self.assertEqual(result, {"answer": "polled"})
        backend._resume_search_result.assert_not_called()
        backend._wait_search_result.assert_called_once_with("conv-1", 300.0, 3.0)

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

        result = backend._resume_search_result("conv-1", "resume-token", timeout_secs=17.5)

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
        self.assertEqual(request.kwargs["timeout"], 17.5)
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

    def test_resume_search_result_treats_bare_message_as_patch_boundary(self) -> None:
        response = FakeResponse([
            {"message": {
                "id": "final-1",
                "author": {"role": "assistant"},
                "channel": "final",
                "content": {"content_type": "text", "parts": ["Good"]},
                "status": "finished_successfully",
            }},
            {
                "id": "tool-1",
                "author": {"role": "tool"},
                "content": {"content_type": "text", "parts": [""]},
                "status": "in_progress",
            },
            {"p": "/message/content/parts/0", "o": "append", "v": " LEAK"},
            "[DONE]",
        ])
        backend = OpenAIBackendAPI(access_token="token")
        backend.session.post = mock.Mock(return_value=response)

        result = backend._resume_search_result("conv-1", "resume-token")

        self.assertEqual(result["answer"], "Good")

    def test_resume_search_result_retains_nonterminal_final_without_handoff(self) -> None:
        response = FakeResponse([
            {"message": {
                "id": "final-usable",
                "author": {"role": "assistant"},
                "channel": "final",
                "content": {"content_type": "text", "parts": ["Usable answer"]},
                "status": "in_progress",
            }},
            "[DONE]",
        ])
        backend = OpenAIBackendAPI(access_token="token")
        backend.session.post = mock.Mock(return_value=response)

        result = backend._resume_search_result("conv-1", "resume-token")

        self.assertEqual(result["answer"], "Usable answer")
        self.assertEqual(result["status"], "in_progress")

    def test_resume_search_result_new_empty_final_retains_old_result(self) -> None:
        response = FakeResponse([
            {"message": {
                "id": "final-old",
                "author": {"role": "assistant"},
                "channel": "final",
                "content": {"content_type": "text", "parts": ["Old answer"]},
                "status": "finished_successfully",
            }},
            {"message": {
                "id": "final-new",
                "author": {"role": "assistant"},
                "channel": "final",
                "content": {"content_type": "text", "parts": [""]},
                "status": "in_progress",
            }},
            {"p": "/message/status", "o": "replace", "v": "finished_successfully"},
            "[DONE]",
        ])
        backend = OpenAIBackendAPI(access_token="token")
        backend.session.post = mock.Mock(return_value=response)

        result = backend._resume_search_result("conv-1", "resume-token")

        self.assertEqual(result["answer"], "Old answer")
        self.assertEqual(result["assistant_message_id"], "final-old")

    def test_resume_search_result_new_nonempty_final_replaces_old_result(self) -> None:
        response = FakeResponse([
            {"message": {
                "id": "final-old",
                "author": {"role": "assistant"},
                "channel": "final",
                "content": {"content_type": "text", "parts": ["Old answer"]},
                "status": "finished_successfully",
            }},
            {"message": {
                "id": "final-new",
                "author": {"role": "assistant"},
                "channel": "final",
                "content": {"content_type": "text", "parts": [""]},
                "status": "in_progress",
            }},
            {"p": "/message/content/parts/0", "o": "append", "v": "New answer"},
            "[DONE]",
        ])
        backend = OpenAIBackendAPI(access_token="token")
        backend.session.post = mock.Mock(return_value=response)

        result = backend._resume_search_result("conv-1", "resume-token")

        self.assertEqual(result["answer"], "New answer")
        self.assertEqual(result["assistant_message_id"], "final-new")

    def test_resume_search_result_preserves_structured_sources_during_patches(self) -> None:
        response = FakeResponse([
            {"message": {
                "id": "final-source",
                "author": {"role": "assistant"},
                "channel": "final",
                "content": {
                    "content_type": "text",
                    "parts": ["", {"title": "Structured", "url": "https://source.example"}],
                },
                "status": "in_progress",
            }},
            {"p": "/message/content/parts/0", "o": "append", "v": "Patched answer"},
            {"p": "/message/status", "o": "replace", "v": "finished_successfully"},
            "[DONE]",
        ])
        backend = OpenAIBackendAPI(access_token="token")
        backend.session.post = mock.Mock(return_value=response)

        result = backend._resume_search_result("conv-1", "resume-token")

        self.assertEqual(result["answer"], "Patched answer")
        self.assertIn({
            "title": "Structured",
            "url": "https://source.example",
            "snippet": "",
            "source_type": "",
        }, result["sources"])


if __name__ == "__main__":
    unittest.main()
