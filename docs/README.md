# Documentación de Fly-In

Esta carpeta es **la guía de construcción del proyecto desde cero**. Está
escrita para que alguien que nunca ha visto el repositorio pueda levantarlo
entero, pieza a pieza, sin tener que adivinar nada ni leerse el código para
entender qué hace falta.

El `README.md` de la raíz es otra cosa: es la carta de presentación que exige
el subject (Cap. VIII) y va dirigida al evaluador. Aquí vive el detalle.

---

## Dos capas de documentación

La guía está dividida en dos capas, y conviene no mezclarlas:

| Capa | Qué contiene | Cuándo la lees |
|---|---|---|
| **Referencia** (`0X-*.md`, esta carpeta) | *Qué* hay que construir y *por qué*: reglas del subject, formato de datos, arquitectura, teoría del algoritmo, plan de pruebas | Antes de empezar, y cada vez que dudes de una regla |
| **Subproyectos** (`build/SPXX-*.md`) | *Cómo* construir cada pieza: paso a paso, con interfaces cerradas, conceptos explicados, errores clásicos y tests de cierre | Mientras programas esa pieza concreta |

Un **subproyecto** es una unidad de trabajo que se empieza y se termina: tiene
prerequisitos explícitos, un contrato de código, una lista de pasos y un
criterio de salida verificable. Si el criterio de salida pasa, la pieza está
hecha y no vuelves a tocarla salvo que cambie el diseño.

---

## Referencia

| Archivo | Contenido |
|---|---|
| [`00-el-problema.md`](./00-el-problema.md) | Las reglas del subject extraídas del PDF y ordenadas: ocupación, movimiento, costes, salida, puntuación. **La fuente normativa.** |
| [`01-roadmap.md`](./01-roadmap.md) | Los 12 subproyectos, en orden, con su grafo de dependencias y qué desbloquea cada uno |
| [`02-arquitectura.md`](./02-arquitectura.md) | Diseño orientado a objetos: módulos, clases, diagrama de clases, decisiones justificadas |
| [`03-formato-datos.md`](./03-formato-datos.md) | Gramática del archivo de mapa y formato exacto de la salida de simulación |
| [`04-algoritmo.md`](./04-algoritmo.md) | Teoría: Dijkstra → Cooperative A\* → WHCA\*. Por qué cada escalón existe |
| [`05-plan-de-pruebas.md`](./05-plan-de-pruebas.md) | Qué se prueba en cada subproyecto, mapas de prueba y matriz de benchmarks |
| [`06-glosario.md`](./06-glosario.md) | Todos los términos del proyecto definidos, sin dar nada por sabido |
| [`Fly-In.pdf`](./Fly-In.pdf) | El subject original. Ante cualquier contradicción con esta guía, **manda el PDF** |

## Subproyectos

| Subproyecto | Qué construye | Estado |
|---|---|---|
| [`SP00`](./build/SP00-setup.md) | Repositorio, `Makefile`, entorno, linters | ✅ hecho |
| [`SP01`](./build/SP01-modelo-dominio.md) | `Zone`, `Connection`, `Graph` | ✅ hecho |
| [`SP02`](./build/SP02-parser.md) | `MapParser` + mapas de prueba | ✅ hecho |
| [`SP03`](./build/SP03-cli-y-errores.md) | Lectura de fichero, argumentos de línea de comandos, errores limpios | ✅ hecho |
| [`SP04`](./build/SP04-dijkstra.md) | `Dijkstra`: ruta óptima de **un** dron | ✅ hecho |
| [`SP05`](./build/SP05-heuristica-abstracta.md) | `AbstractDistance`: la heurística `h(n)` | ✅ hecho |
| [`SP06`](./build/SP06-tabla-reservas.md) | `ReservationTable`: ocupación espacio-temporal | ▶️ siguiente |
| [`SP07`](./build/SP07-whca.md) | `WhcaPathfinder`: búsqueda cooperativa con ventana | ⬜ pendiente |
| [`SP08`](./build/SP08-drone-y-simulador.md) | `Drone` + `Simulator`: el bucle turno a turno | ⬜ pendiente |
| [`SP09`](./build/SP09-formato-salida.md) | `OutputFormatter`: la salida exacta del subject | ⬜ pendiente |
| [`SP10`](./build/SP10-visualizacion.md) | Render en terminal a color (y gráfico opcional) | ⬜ pendiente |
| [`SP11`](./build/SP11-benchmarks-y-readme.md) | Medición contra benchmarks, ajuste y `README.md` final | ⬜ pendiente |

---

## Cómo usar esta guía

1. **Lee [`00-el-problema.md`](./00-el-problema.md) entero antes de nada.** Son
   las reglas del juego. Media docena de bugs clásicos de este proyecto salen de
   no haber leído bien una de esas reglas.
2. **Abre el subproyecto que toca** según [`01-roadmap.md`](./01-roadmap.md).
   Cada uno te dice qué necesitas tener hecho antes de empezar.
3. **No avances sin pasar el criterio de salida.** El orden de los subproyectos
   no es estético: cada uno se apoya en que el anterior ya esté verificado. Si
   SP07 falla y SP05/SP06 están verdes, el bug está en SP07 — eso es todo el
   valor de este orden.
4. **Anota tus decisiones.** Cada subproyecto tiene una sección
   `## Decisiones tomadas`. Rellénala mientras está fresca; es tu argumentario
   literal para la peer-review, donde te van a pedir justificar por qué hiciste
   las cosas así y no de otra forma.

## Convenciones de la guía

- Los bloques marcados **⚠️ No lo des por sentado** explican un concepto que
  podría parecer obvio pero que es donde la gente se atasca.
- Los bloques **🔍 Verifica** son comprobaciones manuales de un minuto que te
  ahorran horas de depuración.
- El código en los subproyectos son **contratos** (firmas + docstrings), no
  implementaciones. La implementación la escribes tú: el subject exige que
  puedas explicar y modificar tu propio código en la evaluación.
