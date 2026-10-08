# Cambios de la entrega

Lo que cambió entre la versión anterior (commit `70830cf`, "Update project
version to Fly-In 2.0") y la entregada. El algoritmo, el simulador, el parser
y la salida del subject **no cambian**: los benchmarks dan los mismos turnos
(10 de 10 en objetivo, challenger en 43).

| Cambio | Ficheros | Tests |
|---|---|---|
| Ventana pygame mínima | `fly_in/visualization/pygame_view.py` | Los mismos de `test/test_session.py` |
| Flag `--capacity-info` | `fly_in/simulation/capacity_observer.py` (nuevo), `fly_in/main.py`, `Makefile` | `test/test_capacity_observer.py` (nuevo, 14) |
| Comentarios y docstrings en inglés | Todo `fly_in/`, `test/` y los mapas propios | — |
| Documentación reunida en `entrega/` | `docs/` desaparece | — |

Estado final: flake8 y `mypy --strict` limpios en 42 ficheros, **425
tests** (411 + 14).

---

## 1. La ventana pygame mínima

**Antes** ("modo misión"): fondo oscuro con degradado, rejilla y 220
estrellas; zonas hexagonales con halo (`Glow`), anillo ámbar giratorio en las
`restricted`, estrella dorada en las `priority`, puntos de capacidad;
drones como cuadricópteros con hélices, sombra y estela; flujo de luz en las
conexiones usadas; chispas y "+1" en las entregas (`Particle`); anillo
"WHCA\* REPLAN"; tarjeta de *briefing* con cuenta atrás 3-2-1-GO y tarjeta
final `MISSION COMPLETE` con seis métricas.

**Ahora**: fondo blanco; zonas como círculos **pastel** con borde fino y,
debajo, `nombre ocupados/max_drones` (borde y etiqueta en rojo si la zona
está llena); drones como **puntos saturados con borde oscuro** y su número;
conexiones grises, más gruesas cuanto más capacidad, a trazos hacia una
`restricted`; una **línea de estado** arriba (mapa, `turn k/N`,
`delivered d/n`, teclas), que también lleva la cuenta atrás y el resumen
final `done in N turns (target T)`.

**Por qué:** la ventana tiene que servir para **comprobar de un vistazo que la
partida es correcta**. En mapas densos como el challenger, los halos, estelas
y efectos tapaban justo lo que hay que mirar (quién está dónde, qué zona está
llena) y un dron del mismo tono que su zona se perdía. Zona pastel + dron
saturado con borde oscuro se distinguen siempre.

**En el código:**

| Qué | Antes | Ahora |
|---|---|---|
| Líneas de `pygame_view.py` | 882 | 438 |
| Clases | `PygameView`, `Projection`, `Glow`, `Fonts`, `Particle` | `PygameView`, `Projection` |
| Capas de `_paint` | 8 (fondo, estrellas, conexiones, zonas, drones, efectos, etiquetas, tarjeta) | 5 (fondo, conexiones, zonas, drones, línea de estado) |
| Curva de movimiento | Cúbica (`4p³`) | *Smoothstep* (`p²·(3 − 2p)`) |
| Tamaño por defecto / mínimo | 1280×800 / 900×600 | 1200×760 / 800×560 |
| Radio de zona | 9–24 px | 10–26 px |
| Color de zona | El de `color=` (o tipo), aclarado si era muy oscuro (`_visible`) | Mezclado un 62 % con blanco (`PASTEL`); sin `color=`, por tipo, verde `start_hub`, azul `end_hub` |
| Color de dron | `Palette.drone_color` | El mismo, oscurecido si es muy claro sobre blanco (`_on_white`) |
| `countdown` | Tarjeta de briefing | `starting in N` / `GO` en la línea de estado |
| `finish` | Tarjeta `MISSION COMPLETE` | `done in N turns (target T) · press any key to close` |

Lo que no cambia: `Session`, `Scene`, `EventLog`, `Palette`, las teclas
(`SPACE`, `ESC`/`Q`), el `with`, el import perezoso de pygame,
`PYGAME_HIDE_SUPPORT_PROMPT` y todos los tests de la ventana. `Scene` sigue
calculando `used`, `airborne` y `replan_turns`, que la ventana mínima ya no
dibuja; las replanificaciones y las esperas las cuenta el log. Las métricas
detalladas siguen en el resumen del log (`MISSION COMPLETE`) y con
`--metrics`.

Las capturas de [`img/`](./img/) son de la ventana nueva; la del briefing se
borró.

Documentación al día: [`defensa/fase-visual.md`](./defensa/fase-visual.md)
(reescrito), [`defensa/13-defensa-visualizacion.md`](./defensa/13-defensa-visualizacion.md),
[`narrativas/SP10-narrativa.md`](./narrativas/SP10-narrativa.md),
[`build/SP10-visualizacion.md`](./build/SP10-visualizacion.md),
[`referencia/07-diagramas.md`](./referencia/07-diagramas.md) (F1, F7, SP10),
[`diagramas/E.4`](./diagramas/E.4-render-pipeline.md) y
[`diagramas/E.5`](./diagramas/E.5-drone-color.md).

## 2. `--capacity-info`

La hoja de evaluación propone como modificación en directo un flag que
enseñe, turno a turno, `Zone X: Y/Z drones, Connection A-B: Y/Z capacity
used`. Antes solo existía como ensayo (un parche aparte); ahora está en el
código:

- **`CapacityObserver`** (`fly_in/simulation/capacity_observer.py`): un
  observador del simulador (cumple el `Protocol` `SimulationObserver`) que,
  tras cada turno, guarda en `lines` la ocupación de cada zona (los drones
  en el aire no cuentan) y el uso de cada conexión (un `Move` = una conexión
  usada; un tránsito a `restricted` la ocupa los dos turnos).
- **`main.py`**: el argumento `--capacity-info`; con él, el simulador recibe
  `ObserverGroup(recorder, capacity)`; al escribir `stdout`, tras cada línea
  de turno se vacía `stdout` y se escribe su línea `T<k> …` en `stderr`.
  Sin el flag, el comportamiento no cambia ni un byte.
- **`Makefile`**: `make capacity MAP=… ARGS=…`.
- **Tests** (`test/test_capacity_observer.py`, 14): una línea por turno,
  `bottleneck.txt` a mano, el tránsito a `restricted`, ningún uso por encima
  de su capacidad en los 10 mapas oficiales, y `stdout` intacto con el flag.

```console
$ make capacity MAP=maps/valid/bottleneck.txt ARGS=-q
D1-narrow
T1 Zone narrow: 1/1 drones, Zone start: 2/inf drones, Connection start-narrow: 1/1 capacity used
…
```

[`ensayo/diff-flag.patch`](./ensayo/diff-flag.patch) se regeneró: ahora es
exactamente este cambio, así que `git apply -R` lo quita (411 tests, lint
limpio) para reescribirlo en directo. Las copias de la variante de ensayo
(`ensayo/capacity_observer.py` y `ensayo/test_capacity_observer.py`, que
escribían en `stderr` mientras simulaban) se borraron.

Documentación: [`defensa/guia-live-coding.md`](./defensa/guia-live-coding.md)
(reescrita sobre el código real) y [`diagramas/E.6`](./diagramas/E.6-live-coding-flow.md).

**A tener en cuenta:** `run` empareja la línea `index` de
`OutputFormatter.format_trace(trace)` con `capacity.lines[index]`.
`format_trace` no escribe línea para un turno sin movimientos, así que un
turno vacío desalinearía las dos listas. Con WHCA\* no ocurre (se comprobó en
todos los mapas con W = 1, 2, 4, 8 y 16), pero es lo primero que revisar si
se cambia el simulador.

## 3. Comentarios en inglés

Todos los comentarios y docstrings de `fly_in/` y `test/` están en inglés,
igual que ya lo estaban los mensajes al usuario. También los comentarios de
los mapas propios (`maps/valid/` y `maps/errors/`) y la descripción de
`pyproject.toml`. La traducción se verificó con el `ast` de Python: quitando
los docstrings y las cadenas, el árbol de cada fichero es idéntico al de
antes. Las únicas cadenas que cambian son:

- `EventLog._legend`: `+N más` → `+N more` (era el único texto en español que
  podía salir por pantalla);
- los mensajes de los `assert` de los tests y dos mapas de prueba escritos
  dentro de los tests (`# only comments`).

## 4. Documentación reunida en `entrega/`

`docs/` desaparece; todo está en `entrega/` y versionado (antes `entrega/`
estaba pensada como no versionada; la línea comentada de `.gitignore` se
quitó).

| Antes | Ahora |
|---|---|
| `docs/README.md` y `entrega/00-indice.md` | [`README.md`](./README.md) (un solo índice) |
| `docs/Fly-In.pdf`, `docs/Intra-Projects-Fly-in-Edit.md`, `docs/Fly_in.drawio` | `subject/Fly-In.pdf`, `subject/hoja-evaluacion.md`, `subject/Fly_in.drawio` |
| `docs/00`…`docs/07` | `referencia/00`…`referencia/07` |
| `docs/build/` | `build/` |
| `docs/08`…`docs/12` (narrativas) | Ya estaban copiadas en `narrativas/`; queda una sola copia |
| `docs/13`, `docs/14`, `entrega/cumplimiento-hoja-evaluacion.md`, `fase-visual.md`, `guia-live-coding.md` | `defensa/` |
| `docs/img/` | `img/` |

Todos los enlaces relativos se reescribieron y se comprobaron (ninguno roto),
incluidos los del `README.md` de la raíz, cuyas capturas apuntan ahora a
`entrega/img/`. `test/test_whca.py` cita la guía en su nueva ruta
(`entrega/build/SP07-whca.md`).

Los recuentos citados en los documentos se pusieron al día: 425 tests,
42 ficheros para mypy.
