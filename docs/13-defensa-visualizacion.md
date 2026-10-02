# Defensa de la visualización (SP10)

Este documento es para **estudiar y defender** la parte visual en la
evaluación. La [narrativa de SP10](./11-narrativa-sp10.md) cuenta cómo se
construyó y los [diagramas de SP10](./07-diagramas.md#sp10--visualización)
dibujan cada flujo. Aquí está lo que un evaluador puede preguntar y cómo
responder, pieza por pieza, con el sitio exacto del código y el test que lo
demuestra.

Cómo usarlo:

1. Lee §1 (qué exige el subject) y §2 (el mapa de piezas). Con eso puedes
   explicar la arquitectura en dos minutos.
2. Estudia §3, un apartado por fichero. Cada uno termina con las preguntas
   probables.
3. Ensaya la demo de §5 antes de la evaluación.

---

## 1. Qué exige el subject y dónde se cumple

| Frase del subject | Dónde se cumple |
|---|---|
| *"Your implementation must provide visual feedback of the simulation, either through colored terminal output … or a graphical interface … or both"* (Cap. VII.1) | Las **dos** cosas: una ventana gráfica con pygame (`pygame_view.py`) **y** un log de eventos a color en la terminal (`event_log.py`) |
| *"When colors are specified, the implementation should provide visual feedback through colored terminal output or graphical representation"* (Cap. VI) | `Palette.resolve` convierte el `color=` de cada zona, en la terminal y en la ventana |
| *"Accepted values for color are any valid single-word strings … There is no fixed list"* (Cap. VI) | Ninguna palabra falla: tabla conocida → `rainbow` → `#rrggbb` → tono derivado del hash (§3.6) |
| *"How does your visual representation enhance understanding of the simulation?"* (Cap. VII.1) | §4 de este documento: la respuesta preparada |
| *"Quality and usefulness of visual representation"* (métrica secundaria, Cap. VII.6) | Capacidad visible, tránsitos visibles, replanificaciones visibles, y en el log la línea de `stdout` de cada turno |
| *"The simulation must output the step-by-step movement"* (Cap. VII.5) | La visualización **nunca** toca `stdout`: la ventana, o `stderr` ([F2](./07-diagramas.md#f2--los-dos-canales-de-salida-stdout-y-stderr)) |
| *"If your program crashes due to unhandled exceptions … non-functional"* (Cap. III.1) | Sin pygame, sin pantalla, sin terminal, si se cierra la ventana o si se corta la tubería: el programa sigue o sale limpio ([F3](./07-diagramas.md#f3--frontera-de-excepciones-y-códigos-de-salida)) |
| *"Prefer context managers for resources"* (Cap. III.1) | `with PygameView(...)` (cierra pygame) ([F8](./07-diagramas.md#f8--recursos-y-su-liberación)) |
| *"Any library that helps with graph logic is forbidden"* (Cap. V) | pygame solo dibuja: no sabe nada de grafos ni de rutas. Toda la lógica de grafos es propia |

---

## 2. El mapa de piezas

```
fly_in/visualization/
├── session.py        Session, Run, AnimatedView   qué vista, y el bucle que la enseña
├── recorder.py       ReplayRecorder               observador: posiciones y línea de cada turno
├── scene.py          Scene, Spot, LinkUse         los fotogramas precalculados (sin pygame)
├── pygame_view.py    PygameView                   la ventana: abrir, animar, cerrar
│                     Projection, Glow, Fonts,     piezas del dibujo
│                     Particle
├── event_log.py      EventLog                     el log de la terminal
└── palette.py        Palette, Painter             colores y códigos ANSI
```

**La idea que lo ordena todo:** *la visualización no calcula nada*. El
simulador produce la traza (`List[List[Move]]`) y los estados de los drones.
Todo lo visual **lee** eso. Si la pantalla y `stdout` no coincidieran, el fallo
estaría en el simulador, porque no hay dos lógicas distintas que puedan
divergir.

**El orden de una ejecución** (`FlyIn.run`):

1. Se simula entero, con `ReplayRecorder` como observador. Tarda milisegundos.
2. Se enseña lo grabado: `Session.play`, a ritmo de `--delay`.
3. Se imprime `stdout` de golpe.

**Las vistas y cuándo se usa cada una:**

| Vista | Qué se ve | Se elige sola cuando… |
|---|---|---|
| `window` | Ventana pygame **y** log en la terminal, turno a turno a la vez | Hay terminal **y** pantalla gráfica |
| `log` | Solo el log de eventos | No hay terminal o no hay pantalla gráfica |
| ninguna | Nada | `-q` / `--quiet` |

**¿Por qué pygame?** El subject pide una interfaz gráfica o terminal a color.
pygame es la biblioteca gráfica de Python más conocida, dibuja con primitivas
simples (líneas, polígonos, círculos) y todo el código queda en Python. Se usa
**pygame-ce** (la edición comunitaria, mantenida activamente): la misma API y
el mismo `import pygame`. La versión clásica 2.6.1 tiene el módulo de fuentes
roto en Python 3.14, y pygame-ce no.

---

## 3. Pieza por pieza

### 3.1 `session.py` — `Session`, `Run` y `AnimatedView`

**Qué hace.** `Run` es una simulación terminada y congelada
(`@dataclass(frozen=True)`): grafo, traza, grabador, métricas, replans,
título, `W` y PAR. `Session` la enseña en la vista `window` o `log`.

| Método | Qué hace |
|---|---|
| `Session.choose_view(requested, quiet, interactive)` | `-q` gana siempre; una vista explícita se respeta; `auto` elige `window` solo con terminal **y** pantalla (`display_available`), y `log` en cualquier otro caso |
| `play()` | Con `window`, intenta `_play_window`; si no se puede, sigue con el log. Al final, el resumen |
| `_play_window()` | Silencia el saludo de pygame, importa `pygame_view`, crea la `Scene`, abre la ventana dentro de un `with`, hace la cuenta atrás y reproduce la partida |
| `_play_log(window)` | Por cada turno: escribe su bloque en el log y, si hay ventana, lo anima durante `pace` segundos; si no, duerme `pace` |

**Decisiones que defender:**

- **Simular primero, enseñar después.** Para animar *entre* dos turnos, la
  ventana tiene que saber adónde va cada dron, y la tarjeta y la barra de
  progreso necesitan saber cuántos turnos hay. Grabar primero da todo eso, y
  además las métricas de tiempo miden solo el cálculo.
- **Un solo hilo.** La terminal y la ventana van a la par porque las mueve el
  mismo bucle: se escribe el bloque del turno `k` y se anima el turno `k`. No
  hay sincronización que pueda fallar ni condiciones de carrera.
- **Import perezoso de pygame.** `pygame_view` se importa dentro de
  `_play_window`, solo cuando se va a abrir una ventana. Por eso `--view log`
  y todos los tests del algoritmo funcionan aunque pygame no esté
  instalado.
- **`AnimatedView` es un `Protocol`** (igual que `DroneLike` en SP07):
  `_play_log` necesita "algo con `closed` y `play_turn`", sin importar la clase
  concreta ni pygame.
- **Replans por instante.** Una replanificación en el instante `T` precede al
  turno `T+1`, por eso el turno `k` enseña `replans.get(k - 1)`.

**Preguntas probables:**

- *¿Qué pasa si no hay pantalla?* `auto` elige `log`. Si fuerzas
  `--view window` y no se puede abrir, sale "cannot open a window · terminal
  only" y la partida sigue en la terminal. `test_no_window_means_terminal_only`.
- *¿Y si pygame no está instalado?* "pygame is not installed · terminal only".
  `test_missing_pygame_means_terminal_only`.
- *¿Y si cierro la ventana a mitad?* Sale "window closed · terminal only" una
  vez y la terminal sigue a su ritmo. `test_closing_the_window_keeps_the_terminal_going`.
- *¿Y si ejecuto `make run > out.txt`?* `stderr` sigue siendo la terminal:
  ves la ventana y el log, y `out.txt` solo tiene las líneas de turno.

### 3.2 El saludo de pygame y `stdout`

Este detalle es el más importante de toda la parte gráfica. Al importarse,
pygame escribe `pygame-ce 2.5.8 (SDL 2.32.10, Python 3.14.7)` **por
`stdout`**. Si no se evitara, la primera línea de la salida del programa no
sería un turno, y la corrección automática fallaría.

`Session._play_window` define `PYGAME_HIDE_SUPPORT_PROMPT=1` justo antes del
import, que es la forma documentada de silenciarlo.
`test_pygame_never_writes_to_stdout` ejecuta el programa de verdad (un
subproceso con la vista `window` y vídeo en memoria), **quitando** esa
variable del entorno, y exige que `stdout` tenga exactamente las cuatro líneas
de `linear.txt`.

### 3.3 `recorder.py` y `scene.py` — los datos de la animación

**`ReplayRecorder`** es un observador (`on_turn`) que guarda, tras cada turno,
dónde está cada dron y la línea de `stdout` del turno:

| Posición | Significado |
|---|---|
| `["z", zona]` | En tierra, en esa zona |
| `["a", origen, destino]` | En el aire hacia una `restricted` |
| `["d"]` | Entregado |

`positions[0]` es la foto inicial (todos en `start_hub`) y hay una más por
turno: `len(positions) == len(trace) + 1`
(`test_recorder_keeps_one_frame_per_turn_plus_the_start`).

**`Scene`** convierte esa grabación, **una sola vez**, en lo que el dibujo
consulta 60 veces por segundo:

| Atributo | Qué es |
|---|---|
| `spots[k][dron]` | Un `Spot`: el punto del mapa donde va (una zona, o el punto medio de la conexión si está en el aire), y su hueco si comparte zona |
| `occupants[k]` | Qué drones hay en cada zona |
| `used[k]` | Qué conexiones se recorren de `k-1` a `k`, en qué sentido y con qué dron |
| `delivered[k]`, `airborne[k]` | Contadores de entregados y drones en el aire (el número sobre `end_hub`) |
| `replan_turns` | Turnos que empiezan con una replanificación |

`scene.py` **no importa pygame**, así que se prueba sin pantalla
(`test_scene_*`): un dron en el aire va al punto medio de su conexión, cada
dron de una zona llena tiene su propio hueco, las conexiones usadas son las
correctas y las entregas se cuentan bien.

### 3.4 `pygame_view.py` — `PygameView`

**Ciclo de vida** ([10.5](./07-diagramas.md#105-la-vida-de-la-ventana)):

| Método | Qué hace |
|---|---|
| `open()` | `pygame.init`, tamaño según la pantalla (1280×800 como mucho), `set_mode`, fuentes. Si pygame lanza `pygame.error` (sin vídeo) o `NotImplementedError` (un módulo roto), cierra y devuelve `False` |
| `countdown(value, seconds)` | La tarjeta de *briefing* con el número en grande |
| `play_turn(turn, seconds)` | Anima de `turn - 1` a `turn` durante `seconds` |
| `finish(metrics, hold)` | La tarjeta final, hasta que se pulse una tecla o pasen `hold` segundos |
| `close()` | `pygame.quit()`; se puede llamar dos veces |
| `__enter__` / `__exit__` | Context manager: pygame se cierra aunque haya un error o Ctrl+C |

**El bucle** ([F7](./07-diagramas.md#f7--un-solo-hilo-el-bucle-de-la-ventana)).
`_animate` llama a `_tick` y a `paint(progreso)` hasta que el progreso llega a
1:

- `_tick` hace `clock.tick(60)` (limita a 60 fps y devuelve cuánto tiempo pasó)
  y vacía la cola de eventos con `pygame.event.get()`. Esto es obligatorio: si
  no se leen los eventos, el sistema marca la ventana como "no responde".
- `QUIT` o `ESC`/`q` → `_close_window`: `pygame.quit()` en el acto y
  `closed = True`. `SPACE` → pausa (el progreso deja de avanzar).
- El progreso es `tiempo transcurrido / seconds`. Con `seconds = 0` se dibuja
  una vez y ya.

**El fotograma** ([10.6](./07-diagramas.md#106-un-fotograma-de-la-ventana)).
`_paint` dibuja por capas, de atrás hacia delante: fondo, estrellas,
conexiones, zonas, drones, efectos, etiquetas y, si toca, la tarjeta. Al final,
`pygame.display.flip()` enseña el fotograma completo de golpe (doble búfer).

**Piezas auxiliares:**

| Clase | Para qué |
|---|---|
| `Projection` | Coordenadas del mapa → píxeles. Una escala por eje (los mapas son muy anchos), sin estirar un eje más de 2,5 veces el otro, y la `y` invertida (en el mapa crece hacia arriba; en pantalla, hacia abajo) |
| `Glow` | Halos de luz: círculos concéntricos cada vez más brillantes hacia el centro, **precalculados una vez por color y radio**, que se suman al fondo con `BLEND_RGB_ADD` |
| `Fonts` | Las tipografías y una caché de textos ya dibujados: dibujar texto es lo más caro de pygame |
| `Particle` | Una chispa de una entrega: se mueve, se frena y se apaga |

**Detalles que suelen preguntar:**

- *¿Cómo se mueve un dron suavemente?* Entre el píxel de su `Spot` en `k-1` y
  en `k` se interpola con una curva cúbica (`_ease`: acelera y frena). La
  elevación (si va en el aire) se interpola igual.
- *¿Por qué la ocupación de las zonas cambia a mitad de la animación?* Porque
  es cuando el dron "llega": los puntos de capacidad pasan del estado `k-1` al
  `k` al 50 % del viaje.
- *¿Cómo se dibuja un dron entregado?* A partir del 60 % del viaje se encoge
  dentro del objetivo, y salen chispas y un "+1".
- *¿No es lento dibujar todo 60 veces por segundo?* Lo caro se hace una vez:
  el fondo, los halos (`Glow`), los textos (`Fonts`) y los fotogramas
  (`Scene`). El bucle solo combina piezas ya hechas.

**Qué cuenta cada elemento visual** (esto es lo que se defiende como
"enhance understanding"):

| Elemento | Qué regla del subject hace visible |
|---|---|
| Puntos de capacidad sobre cada zona; zona en rojo que late al llenarse | `max_drones` (VII.2): por qué un dron espera |
| Dron elevado con sombra sobre la conexión durante dos turnos | Coste 2 de `restricted` y *"MUST reach its destination during the next turn"* (VII.3) |
| Flujo de luz sobre la conexión en el sentido del viaje | Qué conexión ocupa cada dron (`max_link_capacity`) |
| Anillo ámbar giratorio, estrella dorada, cruz roja; conexiones a trazos hacia `restricted` | Tipos de zona (VI) sin leer el fichero |
| Anillo rosa "WHCA\* REPLAN" | Cuándo recalcula el algoritmo ("are you recalculating or caching paths?", VII.1) |
| Número de entregados sobre `end_hub` | Progreso de la partida |
| Tarjeta final: turnos y métricas de los movimientos ejecutados | Métricas secundarias y benchmark (VII.6, VII.7) |

### 3.5 `event_log.py` — `EventLog`

**Qué hace.** Escribe en `stderr` el *briefing* (mapa, escuadrón, motor, PAR,
vista), la cuenta atrás, un bloque por turno y el resumen final
([10.9](./07-diagramas.md#109-eventlogturn-un-bloque-del-log)).

```
 ── T02 ────────────────────────────────────────────────── ▸ D1-goal D2-narrow
   D1   ★ DELIVERED to goal  ████░░░░░░░░ 1/3
   D2   → narrow
   ·    holding at start: D3
```

**Decisiones:**

- **El aviso de zona llena sale solo cuando la zona se llena**, no en cada
  turno que sigue llena. Un log que repite lo mismo deja de leerse.
  `test_capacity_alert_only_when_a_zone_fills`.
- **Con muchos drones esperando se resume** (más de 12: "… +13").
  `test_log_holding_list_is_summarised`.
- **Cada línea hace `flush`**: el log va en directo.
- **No calcula nada**: lee `Move`, las posiciones grabadas y los `Replan`.

### 3.6 `palette.py` — `Palette` y `Painter`

**`Palette.resolve(name, frame)`** convierte el `color=` en RGB: tabla de ~30
nombres → `rainbow` (el tono gira con el tiempo) → `#rrggbb` → cualquier otra
palabra da un tono derivado de su SHA-256 (estable entre ejecuciones).
**Nunca lanza una excepción** (`test_any_color_name_resolves`). La ventana la
usa igual que la terminal, y además aclara los colores muy oscuros
(`PygameView._visible`) para que se vean sobre el fondo.

**`Palette.drone_color(id)`**: D1 a D7 usan la paleta Okabe-Ito (pensada
para daltonismo); desde D8, tonos separados por el ángulo áureo. Es la misma
función en la ventana y en el log, así que cada dron tiene un solo color
(`test_each_drone_has_one_color_in_the_log`).

**`Painter`** es el **único** sitio que escribe códigos ANSI en la terminal:

- Desactivado (sin terminal o con `NO_COLOR`): texto tal cual
  (`test_log_without_color_has_no_ansi`).
- Con `COLORTERM=truecolor`, RGB de 24 bits; si no, el más cercano de los 16
  colores estándar.
- Siempre cierra con `RESET`: el color nunca se queda pegado al prompt.

---

## 4. La respuesta a *"How does your visual representation enhance understanding of the simulation?"*

Prepárala en voz alta; es una pregunta literal del subject (Cap. VII.1):

> La salida del subject es una lista de líneas `D1-roof1 D2-corridorA`. Es
> correcta pero no explica nada: no dice **por qué** un dron espera ni
> **dónde** está el cuello de botella. La visualización enseña las
> restricciones que explican cada decisión.
>
> - Capacidad: los puntos de cada zona se llenan y la zona se pone roja, así
>   que se ve por qué D3 espera.
> - Tránsitos: el dron se eleva sobre la conexión durante dos turnos, que es
>   el coste de `restricted`.
> - Uso de conexiones: el flujo de luz marca cuál está ocupada y en qué
>   sentido.
> - El algoritmo: cada replanificación de WHCA\* se ve en la ventana (el
>   anillo rosa) y en el log, con cuántos drones replanificó y cuánto tardó.
>
> Y las dos pantallas se complementan. La ventana da la **visión espacial**
> (el mapa con sus coordenadas reales). El log da el **detalle exacto** de
> cada turno, con la misma línea que sale por `stdout`, para cotejar la
> animación con la salida. Todo esto sin tocar `stdout`, que sigue teniendo
> solo las líneas que se corrigen.

---

## 5. Demo para la evaluación

Los comandos van en orden. Cada uno demuestra una cosa. `python` es el del
entorno: `source .venv/bin/activate` (o `.venv/bin/activate.fish` en fish).

```bash
make install                                         # entorno limpio, con pygame-ce
make run MAP=maps/oficial_maps/medium/02_circular_loop.txt
#   → ventana + log en la terminal, turno a turno a la vez

make run MAP=maps/oficial_maps/challenger/01_the_impossible_dream.txt ARGS="-d 0.3"
#   → 25 drones, rainbow, zonas black aclaradas, replans visibles

make run MAP=maps/oficial_maps/easy/02_simple_fork.txt > out.txt
cat out.txt; wc -l out.txt
#   → stdout limpio: solo líneas de turno, ni rastro del saludo de pygame

NO_COLOR=1 python -m fly_in.main maps/valid/bottleneck.txt --view log
#   → texto plano sin un solo código ANSI

DISPLAY= WAYLAND_DISPLAY= python -m fly_in.main maps/valid/linear.txt
#   → sin pantalla gráfica: vista log, nunca intenta abrir una ventana
```

Qué enseñar en la ventana: pulsa `SPACE` para pausar en un turno con una
zona llena, señala los puntos de capacidad en rojo, compara la cabecera
del turno en la terminal (la línea de `stdout`) con lo que se mueve, cierra la ventana con `ESC` a mitad y
enseña que la terminal sigue.

---

## 6. Tests que respaldan cada afirmación

| Afirmación | Test |
|---|---|
| `-q` gana; `auto` sin terminal o sin pantalla da `log` | `test_quiet_wins_over_everything`, `test_auto_never_opens_a_window_without_a_terminal`, `test_auto_opens_a_window_only_with_a_display` |
| El log cuenta bien cuellos de botella y tránsitos | `test_log_tells_the_bottleneck_story`, `test_log_narrates_the_restricted_transit` |
| Sin color no hay ANSI | `test_log_without_color_has_no_ansi` |
| Cada dron, un solo color (log y ventana) | `test_each_drone_has_one_color_in_the_log` |
| D1–D7: los siete colores Okabe-Ito, ninguno parecido a otro | `test_first_seven_drones_use_distinct_okabe_ito_colors` |
| La escena coloca bien a cada dron y cuenta bien | `test_scene_puts_airborne_drones_on_the_middle_of_the_link`, `test_scene_gives_every_drone_its_own_slot_in_a_crowd`, `test_scene_knows_which_links_each_turn_uses`, `test_scene_counts_deliveries_and_replans` |
| La ventana dibuja todos los turnos de todos los mapas sin fallar | `test_window_draws_every_turn_of_every_map` (19 mapas) |
| Ventana y log avanzan juntos | `test_window_session_plays_in_sync_with_the_log` |
| Cerrar la ventana no para la partida | `test_closing_the_window_keeps_the_terminal_going`, `test_quit_event_closes_the_window_at_once` |
| `SPACE` pausa y reanuda | `test_space_pauses_and_resumes_the_animation` |
| La tarjeta final no espera para siempre | `test_end_card_waits_for_a_key_not_forever` |
| pygame se cierra al salir del `with` | `test_window_is_a_context_manager_that_quits_pygame` |
| Sin ventana o sin pygame, sigue en la terminal | `test_no_window_means_terminal_only`, `test_missing_pygame_means_terminal_only` |
| pygame no escribe en `stdout` | `test_pygame_never_writes_to_stdout` |
| Cualquier nombre de color vale | `test_any_color_name_resolves` |
| `stdout` limpio con visualización | `test_stdout_holds_only_turn_lines_even_with_visuals` |
| `stderr` cerrado no provoca un error de Python | `test_closed_stderr_ends_cleanly` |

Los tests de la ventana usan el driver de vídeo `dummy` de SDL: pygame dibuja
en memoria, así que se ejecutan sin pantalla. Se lanzan con `make test` o,
solo los de la visualización, con
`pytest test/test_session.py test/test_visualization.py -v`.

---

## 7. Límites conocidos (dilos tú antes de que te los pregunten)

- **La ventana necesita una pantalla gráfica.** Por SSH sin pantalla se usa la
  vista `log`, que cuenta lo mismo en texto.
- **La animación dura lo que dura `--delay` × turnos.** Con `-d 0` se enseña
  de golpe; con `-q` no hay visualización y el programa acaba en
  milisegundos.
- **En mapas muy densos se ocultan algunas etiquetas** para que no se
  solapen: los hubs siempre se nombran primero.
- **El tamaño de la ventana es fijo** (hasta 1280×800, según la pantalla). No
  hay zoom: el mapa entero se encaja al abrir.
