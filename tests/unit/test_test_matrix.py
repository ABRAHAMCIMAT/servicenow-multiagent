"""Pruebas del generador de matrices de pruebas — HU-004 (llmops/test_matrix.py)."""

import pytest


def test_list_targets_includes_known_targets():
    from backend.llmops.test_matrix import list_targets

    targets = list_targets()
    assert "clasificador" in targets
    assert "guardrails_entrada" in targets
    assert "conocimiento" in targets


def test_generates_batch_with_mixed_case_types(mock_llm):
    from backend.llmops.test_matrix import generate_batch

    batch = generate_batch(mock_llm, "clasificador", count=9)
    assert batch["generated"] == 9
    assert set(batch["by_type"]) == {"positive", "negative", "edge"}
    assert all(c["id"].startswith("TC-") for c in batch["cases"])
    assert all(c["target"] == "clasificador" for c in batch["cases"])


def test_unknown_target_raises_key_error(mock_llm):
    from backend.llmops.test_matrix import generate_batch

    with pytest.raises(KeyError):
        generate_batch(mock_llm, "objetivo_inexistente", count=5)


@pytest.mark.parametrize("count", [0, -1, 31])
def test_count_out_of_range_raises_value_error(mock_llm, count):
    from backend.llmops.test_matrix import generate_batch

    with pytest.raises(ValueError):
        generate_batch(mock_llm, "clasificador", count=count)


def test_batch_is_hard_capped_even_if_llm_overshoots(mock_llm, monkeypatch):
    """El limite de 30 casos/lote se aplica en codigo, no confiando en que el LLM obedezca el prompt."""
    from backend.llmops.test_matrix import MAX_BATCH_SIZE, generate_batch

    oversized = {
        "cases": [
            {"type": "positive", "input": f"caso {i}", "expected_behavior": "x", "rationale": "y"}
            for i in range(50)
        ]
    }
    monkeypatch.setattr(mock_llm, "chat_json", lambda system, user, **kw: oversized)

    batch = generate_batch(mock_llm, "clasificador", count=MAX_BATCH_SIZE)

    assert batch["generated"] == MAX_BATCH_SIZE
