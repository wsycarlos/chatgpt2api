# Search Stream Handoff Design

## Problem

The search endpoint starts a ChatGPT Web conversation and then polls the
conversation-detail endpoint for the final assistant message. Newer ChatGPT
turns can return a `stream_handoff` from the initial SSE response and deliver
the actual answer through the conversation-resume endpoint. For temporary or
not-yet-persisted conversations, conversation-detail polling can remain empty,
causing the endpoint to return an empty `answer`.

## Goals

- Support ChatGPT's resume-SSE handoff transport.
- Preserve the existing conversation-detail polling behavior as a fallback.
- Keep the public `/v1/search` response shape unchanged.
- Exclude reasoning, tool, and other intermediate content from the answer.
- Limit the change to the search implementation and focused regression tests.

## Non-Goals

- Implement ChatGPT's WebSocket topic subscription transport.
- Change the search endpoint's configured model.
- Refactor unrelated conversation or image-generation paths.
- Change account selection, authentication, or public API contracts.

## Design

### Initial Search Stream

The initial `/backend-api/f/conversation` SSE reader will retain three pieces
of state:

- `conversation_id`
- the token from a `resume_conversation_token` payload
- whether a `stream_handoff` payload was observed

The state will be returned as one internal value rather than reducing the
stream immediately to a conversation ID.

### Resume Request

When the initial stream contains both a handoff and a resume token, the backend
will POST to `/backend-api/f/conversation/resume` with:

```json
{
  "conversation_id": "<conversation id>",
  "offset": 0
}
```

The request will use the handoff token as `X-Conduit-Token` and request an SSE
response. Existing authenticated browser-style headers will otherwise be
reused.

### Resumed Result Extraction

The resume reader will process JSON SSE payloads until `[DONE]`. It will only
accept assistant message text belonging to the final response channel. It will
ignore reasoning, thoughts, tool messages, and intermediate channels.

For accepted messages, it will reuse the existing search text and source
extraction behavior. The resulting internal object will have the existing
fields:

- `conversation_id`
- `status`
- `answer`
- `sources`
- `assistant_message_id`
- `create_time`

If multiple final assistant updates arrive, the latest non-empty result will
be retained.

### Fallback Behavior

Conversation-detail polling remains the compatibility fallback. It is used
when:

- no handoff was observed;
- no resume token was supplied;
- the resume request encounters a transient upstream HTTP failure; or
- the resumed stream completes without a usable final answer.

Non-transient upstream errors continue to propagate rather than being hidden.
If resume succeeds with a non-empty final answer, no detail polling is needed.

### Error Handling

Resume HTTP statuses already treated as transient by search polling (`404`,
`409`, `423`, `429`, `500`, `502`, `503`, and `504`) trigger the polling
fallback. Parsing skips malformed or irrelevant SSE payloads while preserving
the latest valid final answer. Missing conversation IDs remain fatal because
neither resume nor polling can proceed without one.

## Testing

Focused unit tests will construct synthetic SSE responses and verify:

1. A handoff with a resume token returns final-channel assistant text.
2. Reasoning or non-final channel text is not returned as the answer.
3. A handoff without a resume token uses conversation-detail polling.
4. A transient resume failure uses conversation-detail polling.
5. A resumed stream with no usable answer uses conversation-detail polling.

The focused tests will be run first, followed by the relevant existing test
suite and project diagnostics.
