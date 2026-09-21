"""Pruebas del registro versionado de prompts (LLMOps)."""
import json

import pytest


# -- PromptTemplate ----------------------------------------------------------
def test_render_substitutes_variables():
    from backend.llmops.prompts import PromptTemplate
    t = PromptTemplate(key="k", template="Hola {nombre}", variables=["nombre"])
    assert t.render(nombre="Carlos") == "Hola Carlos"


def test_render_raises_on_missing_variable():
    from backend.llmops.prompts import PromptTemplate
    t = PromptTemplate(key="k", template="Hola {nombre}", variables=["nombre"])
    with pytest.raises(ValueError, match="Faltan variables"):
        t.render()


def test_render_reports_all_missing_variables():
    from backend.llmops.prompts import PromptTemplate
    t = PromptTemplate(key="k", template="{a} {b}", variables=["a", "b"])
    with pytest.raises(ValueError) as e:
        t.render()
    assert "a" in str(e.value) and "b" in str(e.value)


def test_fingerprint_is_stable():
    from backend.llmops.prompts import PromptTemplate
    a = PromptTemplate(key="k", template="mismo texto")
    b = PromptTemplate(key="k", template="mismo texto")
    assert a.fingerprint() == b.fingerprint()


def test_fingerprint_changes_with_content():
    from backend.llmops.prompts import PromptTemplate
    a = PromptTemplate(key="k", template="texto uno")
    b = PromptTemplate(key="k", template="texto dos")
    assert a.fingerprint() != b.fingerprint()


def test_fingerprint_is_short_hash():
    from backend.llmops.prompts import PromptTemplate
    assert len(PromptTemplate(key="k", template="x").fingerprint()) == 12


def test_to_dict_includes_metadata():
    from backend.llmops.prompts import PromptTemplate
    t = PromptTemplate(key="k", template="x", version="2.1.0",
                       description="desc", variables=["v"])
    d = t.to_dict()
    assert d["key"] == "k" and d["version"] == "2.1.0"
    assert d["description"] == "desc" and d["variables"] == ["v"]
    assert "fingerprint" in d


# -- PromptRegistry ----------------------------------------------------------
def test_registry_get_returns_template():
    from backend.llmops.prompts import PromptRegistry, PromptTemplate
    r = PromptRegistry()
    t = PromptTemplate(key="k", template="x")
    r.register(t)
    assert r.get("k") is t


def test_registry_get_raises_on_unknown_key():
    from backend.llmops.prompts import PromptRegistry
    with pytest.raises(KeyError, match="no registrado"):
        PromptRegistry().get("inexistente")


def test_registry_render_shortcut():
    from backend.llmops.prompts import PromptRegistry, PromptTemplate
    r = PromptRegistry()
    r.register(PromptTemplate(key="k", template="Hola {n}", variables=["n"]))
    assert r.render("k", n="Carlos") == "Hola Carlos"


def test_registry_list_returns_dicts():
    from backend.llmops.prompts import PromptRegistry, PromptTemplate
    r = PromptRegistry()
    r.register(PromptTemplate(key="k", template="x"))
    items = r.list()
    assert len(items) == 1 and isinstance(items[0], dict)


def test_registry_export_is_valid_json():
    from backend.llmops.prompts import PromptRegistry, PromptTemplate
    r = PromptRegistry()
    r.register(PromptTemplate(key="k", template="x"))
    data = json.loads(r.export())
    assert isinstance(data, list) and data[0]["key"] == "k"


def test_registry_overwrites_same_key():
    from backend.llmops.prompts import PromptRegistry, PromptTemplate
    r = PromptRegistry()
    r.register(PromptTemplate(key="k", template="v1"))
    r.register(PromptTemplate(key="k", template="v2"))
    assert len(r.list()) == 1 and r.get("k").template == "v2"


# -- registro global del sistema --------------------------------------------
def test_system_registry_has_classifier_prompt():
    from backend.llmops.prompts import registry
    t = registry.get("clasificador")
    assert "user_message" in t.variables
    assert t.version


def test_system_registry_has_knowledge_prompt():
    from backend.llmops.prompts import registry
    t = registry.get("conocimiento")
    assert set(t.variables) == {"query", "article"}


def test_system_classifier_prompt_renders():
    from backend.llmops.prompts import registry
    out = registry.render("clasificador", user_message="no puedo entrar al CRM")
    assert "no puedo entrar al CRM" in out
    assert "intent" in out


def test_system_prompts_are_versioned():
    from backend.llmops.prompts import registry
    for item in registry.list():
        assert item["version"], f"{item['key']} sin version"
        assert item["fingerprint"]
