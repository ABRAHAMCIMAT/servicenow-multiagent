.DEFAULT_GOAL := help
PY := python3
PIP := $(PY) -m pip

.PHONY: help install dev test test-unit test-int test-e2e cov lint fmt typecheck \
        security ci docker-build up down logs clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:  ## Instala dependencias de produccion
	$(PIP) install -r requirements.txt

dev:  ## Instala dependencias de desarrollo
	$(PIP) install -r requirements-dev.txt

test:  ## Ejecuta todas las pruebas
	pytest

test-unit:  ## Solo pruebas unitarias
	pytest -m unit

test-int:  ## Solo pruebas de integracion
	pytest -m integration

test-e2e:  ## Solo pruebas end-to-end
	pytest -m e2e

cov:  ## Pruebas con cobertura HTML
	pytest --cov=backend --cov-report=html --cov-report=term-missing
	@echo "Reporte: htmlcov/index.html"

lint:  ## Lint con ruff
	ruff check backend tests

fmt:  ## Formatea el codigo
	ruff format backend tests
	ruff check --fix backend tests

typecheck:  ## Verificacion de tipos
	mypy backend

security:  ## Auditoria de seguridad
	bandit -r backend -ll

ci: lint test  ## Equivalente local del pipeline CI

docker-build:  ## Construye la imagen
	docker compose build

up:  ## Levanta el stack
	docker compose up -d
	@echo "API: http://localhost:8000"

down:  ## Detiene el stack
	docker compose down

logs:  ## Sigue los logs
	docker compose logs -f api

clean:  ## Limpia artefactos
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
