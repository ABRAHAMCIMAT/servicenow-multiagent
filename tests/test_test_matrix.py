"""Generador de matrices de pruebas — HU-004 (backend/llmops/test_matrix.py)."""
from __future__ import annotations

import pytest

from backend.core.llm import LLM
from backend.llmops.test_matrix import MAX_BATCH_SIZE, generate_batch, list_targets


@pytest.fixture
def llm():
    return LLM()


def test_list_targets_includes_known_targets():
    targets = list_targets()
    assert "clasificador" in targets
    assert "guardrails_entrada" in targets


def test_generates_batch_with_mixed_case_types(llm):
    batch = generate_batch(llm, "clasificador", count=9)
    assert batch["generated"] == 9
    assert set(batch["by_type"]) == {"positive", "negative", "edge"}
    assert all(c["id"].startswith("TC-") for c in batch["cases"])
    assert all(c["target"] == "clasificador" for c in batch["cases"])


def test_unknown_target_raises_key_error(llm):
    with pytest.raises(KeyError):
        generate_batch(llm, "objetivo_inexistente", count=5)


@pytest.mark.parametrize("count", [0, -1, MAX_BATCH_SIZE + 1])
def test_count_out_of_range_raises_value_error(llm, count):
    with pytest.raises(ValueError):
        generate_batch(llm, "clasificador", count=count)


def test_batch_is_hard_capped_even_if_llm_overshoots(llm, monkeypatch):
    # Simula un LLM que ignora la instrucción del prompt y devuelve más
    # casos que el límite — el truncado debe aplicarse en código, no confiar
    # solo en que el modelo obedezca.
    oversized = {"cases": [
        {"type": "positive", "input": f"caso {i}", "expected_behavior": "x", "rationale": "y"}
        for i in range(50)
    ]}
    monkeypatch.setattr(llm, "chat_json", lambda system, user, **kw: oversized)

    batch = generate_batch(llm, "clasificador", count=MAX_BATCH_SIZE)

    assert batch["generated"] == MAX_BATCH_SIZE
