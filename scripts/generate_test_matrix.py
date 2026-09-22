"""
Generador de matrices de pruebas (HU-004) — CLI.

Genera, usando el LLM, un lote de casos de prueba (positivos, negativos y de
borde/límite, máx. 30 por lote) para un agente o endpoint del sistema, y los
guarda en un archivo JSON.

Uso:
    python3 scripts/generate_test_matrix.py --list-targets
    python3 scripts/generate_test_matrix.py --target clasificador --count 15
    python3 scripts/generate_test_matrix.py --target guardrails_entrada --count 30 --out /tmp/casos.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config
from backend.core.llm import LLM
from backend.llmops.test_matrix import MAX_BATCH_SIZE, generate_batch, list_targets


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera una matriz de pruebas (positivas/negativas/de borde) para un agente o endpoint."
    )
    parser.add_argument("--target", help="Clave del objetivo a probar (ver --list-targets).")
    parser.add_argument("--count", type=int, default=15,
                        help=f"Número de casos a generar, máx. {MAX_BATCH_SIZE} (default: 15).")
    parser.add_argument("--out", default=None,
                        help="Ruta del archivo JSON de salida (default: DATA_DIR/test_matrix_<target>.json).")
    parser.add_argument("--list-targets", action="store_true", help="Lista los objetivos disponibles y sale.")
    args = parser.parse_args()

    if args.list_targets:
        print("Objetivos disponibles:")
        for t in list_targets():
            print(f"  - {t}")
        return 0

    if not args.target:
        parser.error("--target es requerido (o usa --list-targets para ver las opciones).")

    llm = LLM()
    print(f"Generando hasta {args.count} casos para '{args.target}' (proveedor: {llm.config.provider})…")
    try:
        batch = generate_batch(llm, args.target, count=args.count)
    except (KeyError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error al generar la matriz de pruebas: {e}", file=sys.stderr)
        return 1

    out_path = args.out or str(config.DATA_DIR / f"test_matrix_{args.target}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)

    print(f"\nGenerados {batch['generated']}/{batch['requested']} casos: {batch['by_type']}")
    print(f"Guardado en: {out_path}\n")
    for c in batch["cases"]:
        preview = c["input"] if len(c["input"]) <= 70 else c["input"][:67] + "..."
        print(f"  [{c['type']:>8}] {c['id']}: {preview!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
