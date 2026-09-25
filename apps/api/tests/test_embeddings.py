import pytest

from app.adapters.lmstudio import (
    parse_embedding_response,
    parse_structured_completion_content,
    structured_completion_payload,
)


def test_embedding_response_is_reordered_by_input_index() -> None:
    payload = {
        "data": [
            {"index": 1, "embedding": [0.2, -0.1, 0.7]},
            {"index": 0, "embedding": [0.4, 0.0, -0.3]},
        ]
    }

    assert parse_embedding_response(payload, 2) == [[0.4, 0.0, -0.3], [0.2, -0.1, 0.7]]


def test_structured_completion_content_accepts_plain_or_fenced_json() -> None:
    assert parse_structured_completion_content('{"document_date": "2026-09-25"}') == {"document_date": "2026-09-25"}
    assert parse_structured_completion_content('```json\n{"document_date": "2026-09-25"}\n```') == {"document_date": "2026-09-25"}


def test_structured_completion_content_rejects_non_object_json() -> None:
    with pytest.raises(TypeError):
        parse_structured_completion_content("[]")


def test_structured_completion_text_payload_embeds_the_schema() -> None:
    payload = structured_completion_payload("local-model", "Extract the record.", {"type": "object"})

    assert payload["model"] == "local-model"
    assert payload["response_format"] == {"type": "text"}
    assert '"type":"object"' in payload["messages"][0]["content"]


@pytest.mark.parametrize(
    "payload",
    [
        {"data": [{"index": 0, "embedding": [0.1, 0.2]}]},
        {"data": [{"index": 0, "embedding": [0.1, float("inf")]}, {"index": 1, "embedding": [0.3, 0.4]}]},
        {"data": [{"index": 0, "embedding": [0.1, 0.2]}, {"index": 1, "embedding": [0.3]}]},
    ],
)
def test_embedding_response_rejects_incomplete_or_invalid_vectors(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        parse_embedding_response(payload, 2)