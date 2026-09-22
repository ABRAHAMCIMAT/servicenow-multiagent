# 📐 Arquitectura — Modelo C4

Documentación de la arquitectura del sistema usando el
[Modelo C4](https://c4model.com) (Simon Brown): cuatro niveles de detalle
progresivo, como el zoom de un mapa — cada nivel amplía al anterior sin
repetir toda la información.

## Los 4 niveles

| Nivel | Documento | Responde a |
|-------|-----------|------------|
| 1. Contexto | [01_CONTEXTO.md](01_CONTEXTO.md) | ¿Qué es el sistema y quién/qué interactúa con él? |
| 2. Contenedores | [02_CONTENEDORES.md](02_CONTENEDORES.md) | ¿De qué piezas desplegables/ejecutables está hecho? |
| 3. Componentes | [03_COMPONENTES.md](03_COMPONENTES.md) | ¿Qué módulos internos tiene cada contenedor? |
| 4. Código | [04_CODIGO.md](04_CODIGO.md) | ¿Cómo son las clases y los flujos clave a nivel de código? |

## Cómo leer estos documentos

Empieza por el Nivel 1 y solo baja de nivel cuando necesites más detalle —
esa es la idea central de C4: no todos los lectores necesitan el mismo
zoom. Alguien evaluando el proyecto se queda en el Nivel 1 o 2; alguien
integrando un nuevo canal de notificación o depurando un bug probablemente
necesita el Nivel 3 o 4.

Los diagramas usan [Mermaid](https://mermaid.js.org) (`C4Context`,
`C4Container`, `C4Component`, `classDiagram`, `sequenceDiagram`) y se
renderizan automáticamente en GitHub y en la mayoría de editores con
soporte Mermaid (VS Code, GitLab, etc.). Si tu visor no los renderiza, el
código de cada bloque sigue siendo legible como texto — cada diagrama va
acompañado de una tabla o descripción equivalente.

## Relación con la documentación LLMOps

Esta documentación describe la **estructura** del sistema (qué hay y cómo
se conecta). La documentación de [docs/llmops/](../llmops/00_INDICE.md)
describe las **prácticas** aplicadas sobre esa estructura (prompts,
evaluación, guardrails, observabilidad...) fase por fase. Se complementan:
usa C4 para orientarte en el "dónde", y LLMOps para el "cómo y por qué".
