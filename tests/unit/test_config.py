"""Pruebas de la configuracion centralizada (Fase 0)."""

import importlib

import pytest


def test_data_dir_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "d"))
    import backend.config as cfg

    importlib.reload(cfg)
    assert tmp_path / "d" == cfg.DATA_DIR


def test_derived_paths_live_under_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "d"))
    monkeypatch.delenv("LOG_FILE", raising=False)
    monkeypatch.delenv("TELEMETRY_LOG", raising=False)
    monkeypatch.delenv("AUDIT_LOG", raising=False)
    import backend.config as cfg

    importlib.reload(cfg)
    assert str(cfg.DATA_DIR) in cfg.LOG_FILE
    assert str(cfg.DATA_DIR) in cfg.TELEMETRY_LOG
    assert str(cfg.DATA_DIR) in cfg.AUDIT_LOG


def test_cors_defaults_to_localhost_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    import backend.config as cfg

    importlib.reload(cfg)
    assert cfg.CORS_ORIGINS == ["http://localhost:8000", "http://127.0.0.1:8000"]


def test_cors_required_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    import backend.config as cfg

    with pytest.raises(RuntimeError, match="CORS_ORIGINS es obligatoria"):
        importlib.reload(cfg)


def test_cors_rejects_wildcard(monkeypatch):
    """Hallazgo critico de la auditoria: '*' nunca debe permitirse."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    import backend.config as cfg

    with pytest.raises(RuntimeError, match="comodin"):
        importlib.reload(cfg)


def test_cors_parses_multiple_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com, https://b.com")
    import backend.config as cfg

    importlib.reload(cfg)
    assert cfg.CORS_ORIGINS == ["https://a.com", "https://b.com"]


def test_is_production_flag(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com")
    import backend.config as cfg

    importlib.reload(cfg)
    assert cfg.IS_PRODUCTION is True


def test_ensure_dirs_creates_data_dir(monkeypatch, tmp_path):
    target = tmp_path / "nuevo" / "data"
    monkeypatch.setenv("DATA_DIR", str(target))
    import backend.config as cfg

    importlib.reload(cfg)
    cfg.ensure_dirs()
    assert target.is_dir()


def test_no_hardcoded_agent_task_paths_in_code():
    """Regresion Fase 0: ninguna ruta /agent/task ejecutable en el codigo.

    Se ignoran docstrings y comentarios usando el AST (config.py menciona la
    ruta en su docstring descriptivo, lo cual es correcto).
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "backend"
    offenders = []
    for py in root.rglob("*.py"):
        source = py.read_text(encoding="utf-8")
        tree = ast.parse(source)
        # Lineas ocupadas por docstrings / literales de cadena
        string_lines = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for ln in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                    string_lines.add(ln)
        for i, line in enumerate(source.splitlines(), 1):
            if i in string_lines:
                continue
            if line.strip().startswith("#"):
                continue
            if "/agent/task" in line:
                offenders.append(f"{py.relative_to(root)}:{i}")
    assert not offenders, f"rutas absolutas hardcodeadas: {offenders}"
