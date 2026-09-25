import pytest

from app.adapters.lmstudio import parse_embedding_response


def test_embedding_response_is_reordered_by_input_index() -> None:
    payload = {
        "data": [
            {"index": 1, "embedding": [0.2, -0.1, 0.7]},
            {"index": 0, "embedding": [0.4, 0.0, -0.3]},
        ]
    }

    assert parse_embedding_response(payload, 2) == [[0.4, 0.0, -0.3], [0.2, -0.1, 0.7]]


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