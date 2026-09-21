"""
Paquete LLMOps — mejores prácticas para el desarrollo de sistemas
multiagentes conversacionales.

Incluye:
  - logging.py   : logging estructurado (JSON) con niveles y contexto
  - errors.py    : manejo de errores con excepciones tipadas y reintentos
  - prompts.py   : gestión y versionado de prompts
  - evals.py     : evaluación de salidas de los agentes
  - guardrails.py: validación de entradas y salidas
  - patterns.py  : patrones de diseño (registro, estrategia, cadena)
"""

from .errors import LLMOpsError, RetryableError, retry, safe_call
from .evals import EvalResult, Evaluator
from .guardrails import Guardrails
from .logging import get_logger, setup_logging
from .prompts import PromptRegistry, PromptTemplate

__all__ = [
    "get_logger",
    "setup_logging",
    "LLMOpsError",
    "RetryableError",
    "safe_call",
    "retry",
    "PromptRegistry",
    "PromptTemplate",
    "Evaluator",
    "EvalResult",
    "Guardrails",
]
