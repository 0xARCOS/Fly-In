# Cumplimiento del subject, norma a norma

Cada norma del subject ([`Fly-In.pdf`](./Fly-In.pdf), v1.6) con la prueba de
que se cumple: el fichero, el test o el comando que lo demuestra en la
evaluación. Si alguien pregunta "¿dónde cumples X?", la respuesta está en la
tabla correspondiente.

Estado en la última revisión (2026-09-30):

| Comprobación | Resultado |
|---|---|
| `flake8 .` | sin avisos |
| `mypy .` con los flags de `make lint` | `Success: no issues found in 42 source files` |
| `mypy . --strict` | `Success: no issues found in 42 source files` |
| `pytest` | 455 tests, todos pasan |
| Funciones o clases sin docstring en `fly_in/` | 0 |
| Funciones fuera de una clase en `fly_in/` | 0 |
| Benchmarks oficiales | 10 de 10 dentro del objetivo, y el challenger por debajo de 45 |

---

## Cap. III.1 — Reglas generales

| Norma | Cómo se cumple | Cómo demostrarlo |
|---|---|---|
| Python 3.10 o superior | `requires-python = ">=3.10"` en `pyproject.toml`; `mypy` comprueba contra 3.10 (`python_version = "3.10"`) | `make lint` |
| Estándar `flake8` | Todo el repositorio, tests incluidos | `make lint` |
| Excepciones gestionadas, sin *crash* | `FlyIn.main` es la frontera: `MapError`, `SimulationError`, `KeyboardInterrupt` y `BrokenPipeError` se convierten en un mensaje y un código de salida. Por debajo, cada capa traduce sus errores con contexto ([F3](./07-diagramas.md#f3--frontera-de-excepciones-y-códigos-de-salida)) | `test/test_cli.py`: mapas inválidos, fichero ausente, carpeta, no UTF-8, `--window 0`, `--delay nan`, `stderr` cerrado. Ninguno produce un traceback. En `test/test_session.py`: sin pygame, sin ventana posible o cerrando la ventana, la partida sigue en la terminal |
| *Context managers* para recursos | `with PygameView(...)` (ventana y pygame: `pygame.quit()` al salir), `with TerminalRenderer(...)` (cursor). El mapa se lee con `Path.read_text`, que cierra el fichero solo ([F8](./07-diagramas.md#f8--recursos-y-su-liberación)) | `test_window_is_a_context_manager_that_quits_pygame`, `test_cursor_is_restored_when_the_simulation_fails` |
| Sin fugas de recursos | Un solo hilo; cerrar la ventana llama a `pygame.quit()` en el acto; `loading.sh` borra su log temporal también con Ctrl+C | ídem, y `test_quit_event_closes_the_window_at_once` |
| *Type hints* en parámetros, retornos y variables | Todo el paquete y los tests | `make lint-strict` (`mypy --strict` es más exigente que lo que pide el subject) |
| Docstrings PEP 257 en funciones y clases | Todas las funciones, métodos y clases de `fly_in/`, incluidas las anidadas (`Handler`, las funciones `order`) | Ver "Cómo se auditó" abajo |

### Cómo se auditó (docstrings y OOP)

`flake8` y `mypy` no comprueban ni los docstrings ni si hay funciones fuera de
clases. Se revisó con el módulo `ast` de la biblioteca estándar: se recorre
cada fichero de `fly_in/` y se listan (a) los módulos, clases y funciones sin
docstring y (b) las funciones definidas en el nivel del módulo. Resultado: 0 y
0. Para repetirlo en la evaluación:

```bash
python - <<'EOF'
import ast, pathlib
for p in sorted(pathlib.Path("fly_in").rglob("*.py")):
    tree = ast.parse(p.read_text())
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not ast.get_docstring(n):
            print("sin docstring:", p, n.lineno, n.name)
    for n in tree.body:
        if isinstance(n, ast.FunctionDef):
            print("fuera de clase:", p, n.lineno, n.name)
EOF
```

Sin salida = todo en orden.

Los ficheros de `test/` no llevan docstring en cada `test_*`: el subject dice
que los tests *"not submitted or graded"* (Cap. III.3), y el nombre de cada
test ya es la frase que comprueba. Sí pasan `flake8` y `mypy --strict`.

---

## Cap. III.2 — Makefile

| Regla | Qué ejecuta | ¿Coincide con el subject? |
|---|---|---|
| `install` | `python3 -m venv .venv`, `pip install --upgrade pip`, `pip install -e ".[dev]"` | Sí: instala con pip |
| `run` | `.venv/bin/python -m fly_in.main $(MAP) $(ARGS)` | Sí: ejecuta el programa principal |
| `debug` | `.venv/bin/python -m pdb -m fly_in.main $(MAP)` | Sí: `pdb` de la biblioteca estándar |
| `clean` | Borra `.mypy_cache`, `.pytest_cache`, `*.egg-info` y todos los `__pycache__` (sin entrar en `.venv`) | Sí |
| `lint` | `flake8 .` y `mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs` | Sí: los flags exactos |
| `lint-strict` (opcional) | `flake8 .` y `mypy . --strict` | Sí |

Reglas extra: `menu` (la de por defecto), `hud`, `bench`, `test` y
`fclean`. Las pantallas de carga (`scripts/loading.sh`) escriben solo en
`stderr` y **propagan el código de salida** del comando: si `flake8` falla,
`make lint` falla ([SP00](./07-diagramas.md#sp00--setup-y-makefile)).

**Pregunta probable:** *¿las pantallas de carga no esconden los errores?* No:
si un paso falla, se enseñan sus últimas 40 líneas y `make` sale con el mismo
código. `make lint 2>&1 | cat` (sin terminal) da el texto plano de siempre.

## Cap. III.3 — Pautas adicionales

| Pauta | Estado |
|---|---|
| Tests con pytest, con casos límite | 455 tests en `test/` (`make test`) |
| `.gitignore` para artefactos de Python | `__pycache__/`, `*.pyc`, `.venv/`, `*.egg-info/`, `.mypy_cache/`, `.pytest_cache/`, `build/`, `dist/` |
| Entorno virtual | `make install` crea `.venv` |

---

## Cap. V — Restricciones

| Restricción | Cómo se cumple | Cómo demostrarlo |
|---|---|---|
| Ninguna librería de grafos (`networkx`, `graphlib`…) | `Graph`, `Dijkstra`, A\* y WHCA\* son código propio. La única dependencia es `pygame-ce`, que solo dibuja: no sabe nada de grafos ni de rutas | `pyproject.toml`: `dependencies = ["pygame-ce>=2.4"]`. pygame solo se importa en `visualization/pygame_view.py` |
| Completamente *typesafe*: flake8 y mypy obligatorios | Ver Cap. III.1 | `make lint-strict` |
| **Completamente orientado a objetos** | Todo el código vive en clases: 0 funciones en el nivel de módulo en `fly_in/` | Auditoría de arriba y la [Relación 4](./07-diagramas.md#relación-4--mapa-de-clases) |

### Qué cambió para ser "completely object-oriented"

La auditoría encontró 37 funciones sueltas. Se convirtieron en métodos
**sin cambiar su lógica ni su nombre**:

| Antes (función de módulo) | Ahora |
|---|---|
| `clean_lines`, `parse_metadata`, `parse_positive_int`, `parse_zone_type`, `parse_zone_line`, `parse_connection_line` | `@staticmethod` de `MapParser` |
| `by_id`, `farthest_first`, `nearest_first`, `rotating` (whca.py) | `@staticmethod` de `PlanningOrders` |
| `target_for`, `measure`, `main` (benchmarks.py) | `BenchmarkSuite.target_for`, `.measure`, `.report` |
| `positive_int`, `non_negative_float`, `build_parser`, `read_map_file`, `make_painter`, `print_metrics`, `run`, `main` (main.py) | `@staticmethod` de `FlyIn`; el punto de entrada es `FlyIn.main()` |
| `hue`, `resolve`, `drone_color` | `Palette` |
| `supports_truecolor`, `strip_ansi`, `visible_len`, `pad` | `@staticmethod` de `Painter` |
| `plural` | `EventLog.plural` |
| `display_available`, `choose_view`, `play` | `Session.display_available`, `Session.choose_view`, `Session(...).play()` |

**Cómo defender los `@staticmethod`:** una función sin estado dentro de una
clase no es "menos OOP" que un método de instancia. La clase agrupa
responsabilidades (el parser, los criterios de orden, la paleta) y hace de
espacio de nombres. Donde hay estado, hay instancias: `Graph`, `Simulator`,
`Drone`, `ReservationTable`, `WhcaPathfinder`, `Session`, `EventLog`,
`PygameView`, `TerminalRenderer`… Hay también polimorfismo por interfaz:
`SimulationObserver` es un `Protocol` que cumplen `ReplayRecorder`,
`TerminalRenderer` y `ObserverGroup`, y `AnimatedView` uno que cumple
`PygameView`. Las excepciones forman jerarquía (`MapParseError` y
`MapValidationError` heredan de `MapError`).

---

## Cap. VI — Formato del mapa

| Norma | Dónde | Test |
|---|---|---|
| `nb_drones: <n>` en la primera línea | `MapParser.parse` | `test_nb_drones_must_be_a_positive_integer`, `maps/errors/missing_nb_drones.txt` |
| `start_hub:`, `end_hub:`, `hub:` con `<name> <x> <y> [metadata]` | `MapParser.parse_zone_line` | `test_valid_maps_parse`, `test_malformed_zone_lines` |
| Metadatos opcionales en cualquier orden, con valores por defecto | `MapParser.parse_metadata` | `test_zone_defaults`, `test_zone_metadata_in_any_order` |
| Tipos `normal`, `blocked`, `restricted`, `priority` | `MapParser.parse_zone_type` | `maps/errors/invalid_zone_type.txt` |
| `color=` cualquier palabra, sin lista fija | Se guarda tal cual; la visualización nunca falla con un color (`Palette.resolve`) | `test_any_color_name_resolves` |
| `connection: a-b [max_link_capacity=n]`, bidireccional | `MapParser.parse_connection_line`, `Graph.add_connection` | `test_connection_default_and_explicit_capacity`, `test_connection_between_works_in_both_directions` |
| Comentarios con `#` | `MapParser.clean_lines` | `test_comments_and_blank_lines_keep_original_line_numbers` |

## Cap. VII.1 — Algoritmo

| Norma | Cómo se cumple |
|---|---|
| Movimiento simultáneo, maximizar el rendimiento | WHCA\* planifica a todos contra una tabla de reservas común; el simulador aplica todos los movimientos a la vez (dos fases) |
| Reparto por varios caminos | El A\* en espacio-tiempo esquiva lo reservado y encuentra rutas alternativas |
| Espera estratégica | "Esperar" es un sucesor más del A\* |
| Sin conflictos ni bloqueos mutuos | Tabla de reservas (zona, conexión y regla anti-cruce), `_verify` independiente en cada turno, límite de seguridad que nunca deja el programa colgado |
| Costes por tipo de zona | `Zone.movement_cost`: 1, 1, 2; `blocked` no se puede atravesar |
| Capacidades `max_drones` y `max_link_capacity` | `ReservationTable.can_move` en todos los instantes del trayecto |
| Adaptable a cada mapa | Ventana `-w`, criterios de orden intercambiables (`PlanningOrders`), replanificación continua |
| Representación visual | Ventana pygame, log a color y HUD: ver [13](./13-defensa-visualizacion.md) |

Las preguntas del recuadro del Cap. VII.1 (eficiencia, complejidad, caché,
memoria) tienen su respuesta en el `README.md` (sección *Algorithm and
implementation strategy*) y en [04-algoritmo](./04-algoritmo.md).

## Cap. VII.2 y VII.3 — Ocupación y movimiento

| Norma | Test que la fija |
|---|---|
| Como mucho `max_drones` por zona (1 por defecto); `start` y `end` sin límite | `test_invariants_hold_on_valid_maps`, `test_invariants_hold_on_official_maps`, `test_start_and_end_ignore_max_drones_even_if_invalid` |
| `max_link_capacity` por conexión | Mismos tests de invariantes, más `test/test_reservation_table.py` |
| Salir de una zona libera sitio ese mismo turno | `test/test_reservation_table.py` |
| `restricted`: 2 turnos, sin esperar en la conexión | `test_restricted_transit_is_exactly_one_turn_in_the_air`, `test_in_transit_drone_survives_replanning_every_turn` |
| Una violación se detecta en el turno en que ocurre | `test_capacity_violation_is_caught_at_the_turn_it_happens` |

**Interpretación que hay que saber defender:** la conexión hacia una
`restricted` se considera ocupada **los dos turnos** del tránsito (lectura
literal de *"the drone occupies the connection during transit"*). Por eso
`medium/02` da 15 turnos (el objetivo es ≤ 15) y no 10: con una conexión de
capacidad 1 cabe un dron cada dos turnos. Está razonado en
[12-narrativa-sp11](./12-narrativa-sp11.md).

## Cap. VII.4 — Parser

| Norma | Mapa de error o test |
|---|---|
| Número de drones positivo; cualquier cantidad | `test_nb_drones_must_be_a_positive_integer`; el challenger tiene 25 |
| Exactamente un `start_hub` y un `end_hub` | `maps/errors/no_start.txt`, `two_starts.txt`, `test_missing_end_hub` |
| Nombres únicos, coordenadas enteras | `duplicate_zone_name.txt`, `test_malformed_zone_lines`, `test_negative_coordinates_are_valid_integers` |
| Nombres sin guiones ni espacios | `dash_in_name.txt` |
| Conexiones solo entre zonas ya definidas | `connection_unknown_zone.txt`, `test_connection_must_follow_both_zone_definitions` |
| Sin conexiones duplicadas (`a-b` = `b-a`) | `duplicate_connection.txt`, `test_reversed_connection_is_a_duplicate` |
| Metadatos sintácticamente válidos | `malformed_metadata.txt`, `test_invalid_zone_metadata` |
| Tipo de zona inválido = error | `invalid_zone_type.txt` |
| Capacidades enteras positivas | `negative_capacity.txt` |
| `max_drones` ignorado en `start`/`end` | `test_start_and_end_ignore_max_drones_even_if_invalid` |
| Cualquier otro error: parar con la línea y la causa | `test_parse_error_reports_line_number_and_content`, `test_error_maps_fail_with_the_right_cause` |

## Cap. VII.5 — Salida

| Norma | Test |
|---|---|
| Una línea por turno, movimientos separados por un espacio | `test_two_drones_separated_by_one_space`, `test_every_line_has_the_subject_format` |
| `D<ID>-<zona>`, y `D<ID>-<conexión>` en vuelo hacia una `restricted` | `test_transit_prints_connection_then_zone` |
| Los que no se mueven se omiten; los entregados no reaparecen | `test_turn_without_moves_produces_no_line`, `test_delivered_drones_never_reappear` |
| `stdout` solo con las líneas, aunque haya visualización | `test_stdout_holds_only_turn_lines_even_with_visuals` |

## Cap. VII.6 y VII.7 — Puntuación y benchmarks

Resultado con la configuración por defecto (`W = 8`, orden por id), medido con
`make bench`:

| Mapa | Drones | Turnos | Objetivo |
|---|---|---|---|
| easy/01_linear_path | 2 | 4 | ≤ 6 |
| easy/02_simple_fork | 4 | 4 | ≤ 8 |
| easy/03_basic_capacity | 4 | 4 | ≤ 6 |
| medium/01_dead_end_trap | 5 | 8 | ≤ 12 |
| medium/02_circular_loop | 6 | 15 | ≤ 15 |
| medium/03_priority_puzzle | 5 | 7 | ≤ 12 |
| hard/01_maze_nightmare | 8 | 13 | ≤ 30 |
| hard/02_capacity_hell | 12 | 16 | ≤ 35 |
| hard/03_ultimate_challenge | 15 | 26 | ≤ 45 |
| challenger/01_the_impossible_dream | 25 | 43 | récord 45 |

`test_default_configuration_meets_every_target` falla si una mejora futura
rompe alguno. Las métricas secundarias (movimientos por turno, turno medio de
entrega, esperas, pico en el aire, tiempo) salen con `--metrics`, en el log y
en la tarjeta final de la ventana.

## Cap. VIII — README

| Requisito | Estado |
|---|---|
| Primera línea en cursiva, literal | `*This project has been created as part of the 42 curriculum by ariarcos.*` → **confirma que `ariarcos` es tu login** |
| Sección *Description* | Sí |
| Sección *Instructions* | Sí: instalación, ejecución, opciones, reglas del `Makefile` |
| Sección *Resources* con referencias y uso de IA | Sí → **revisa que el apartado "How AI was used" describe cómo lo usaste tú** |
| Descripción del algoritmo y la estrategia | *Algorithm and implementation strategy*, con benchmarks y límites |
| Visualización y cómo mejora la experiencia | *Visual representation* |

## Cap. II — Uso de IA en la evaluación

El subject pide *"Only use AI-generated content that you fully understand and
can take responsibility for"*. Para cumplirlo, esta carpeta tiene lo necesario
para entender cada parte: una guía por subproyecto (`build/`), una narrativa
por etapa (08 a 12), los diagramas de todos los flujos (07) y la defensa de la
visualización (13). La prueba de fuego: poder explicar sin mirar los
diagramas [F1](./07-diagramas.md#f1--make-run-de-principio-a-fin),
[F4](./07-diagramas.md#f4--la-vida-de-un-dron-máquina-de-estados) y
[F5](./07-diagramas.md#f5--una-replanificación-paso-a-paso), y la respuesta de
[13 §4](./13-defensa-visualizacion.md#4-la-respuesta-a-how-does-your-visual-representation-enhance-understanding-of-the-simulation).

---

## Comprobación completa antes de entregar

En una copia limpia del repositorio:

```bash
git clone <repo> /tmp/flyin-check && cd /tmp/flyin-check
make install
make lint && make lint-strict
make test
make bench
make run MAP=maps/oficial_maps/hard/03_ultimate_challenge.txt > out.txt
wc -l out.txt            # 26
make clean && make fclean
```
