# SP10 contado de principio a fin

Continúa [`10-narrativa-sp09.md`](./10-narrativa-sp09.md). Con SP09 el
programa ya es **correcto**: resuelve el mapa y lo dice en el formato exacto.
Este documento cuenta cómo se volvió **visible**: un HUD animado en la
terminal, con aire de videojuego, y una ventana gráfica con pygame. No es
decoración: el subject la exige.

> **Estado.** Implementado en [`fly_in/visualization/`](../fly_in/visualization/)
> y cubierto por [`test/test_visualization.py`](../test/test_visualization.py) y
> [`test/test_session.py`](../test/test_session.py). La guía de pasos es
> [`SP10-visualizacion.md`](./build/SP10-visualizacion.md). Las capturas de
> este documento son salidas reales del programa.
>
> Las secciones 2 a 10 cuentan la primera versión: el HUD en la terminal,
> que sigue disponible como `make hud` (`--view hud`). La sección 11 cuenta
> la que usa hoy `make run`: la partida en una ventana pygame y el log de
> eventos en la terminal, avanzando a la vez.

![La ventana pygame en el challenger, turno 12](./img/window_challenger.png)

---

## 1. El problema: entender sin leer el código

La representación visual está dentro de la parte obligatoria *(Cap. VII.1)*,
cuenta en la evaluación (*"Quality and usefulness of visual representation"*,
Cap. VII.6) y el `README.md` tiene que explicar *cómo mejora la experiencia*
(Cap. VIII). El criterio de salida de la guía lo resume en una frase: alguien
que no ha leído el código tiene que poder ver una ejecución y **entender qué
pasa turno a turno**.

Eso descarta la versión fácil, una lista de posiciones por turno. Lo que hay
que entender en este proyecto son **esperas**: por qué D3 no sale todavía, por
qué D2 da un rodeo, por qué D5 pasa dos turnos en el aire. Y las esperas solo
se explican enseñando **capacidades**: `narrow [1/1 FULL]` explica una espera;
`narrow: D3` no explica nada.

Hay además tres restricciones que no se pueden romper:

- **`stdout` es de SP09.** Todo lo visual va a `stderr`.
- **Cero dependencias.** `dependencies = []` en `pyproject.toml`: nada que
  instalar, nada que pueda faltar en la máquina del evaluador.
- **Nunca un crash por algo decorativo.** El `color=` del mapa admite
  *cualquier* palabra (Cap. VI).

---

## 2. Dos pantallas, un observador

El simulador no sabe que existe una pantalla. En SP10 ganó un único punto de
enganche: `run(observer)`, que tras aplicar cada turno llama a
`observer.on_turn(turn, moves, drones)`. Cualquier objeto con ese método es un
observador (un `Protocol`, igual que `DroneLike` en SP07), y hay dos:

| Observador | Qué hace en cada turno |
|---|---|
| `TerminalRenderer` | Dibuja un fotograma en `stderr` y espera `--delay` segundos |
| `ReplayRecorder` | Anota dónde está cada dron, para la ventana y el log |

`ObserverGroup` reparte cada turno entre los dos cuando se piden ambos. Y como
la animación duerme entre fotogramas, el simulador **descuenta el tiempo que
pasa dentro del observador** al medir su tiempo de cálculo: los 247 ms del
challenger son cálculo, no animación.

La regla de la guía, *el renderer no calcula nada*, se cumple así: lee
`drone.current_zone`, `drone.in_transit` y los `Move`, y cuenta ocupantes para
pintarlos. No decide nada ni vuelve a deducir rutas. Si algún día la pantalla y
la salida no coincidieran, el fallo estaría en el simulador, no en dos lógicas
que se han separado.

---

## 3. La paleta: cualquier palabra es un color

`Palette.resolve(name, frame)` convierte el `color=` de una zona en RGB, en
tres niveles:

1. **Nombres conocidos** (una tabla de ~30: `red`, `crimson`, `gold`,
   `turquoise`…) y `#rrggbb`.
2. **`rainbow`**, que aparece en el challenger: un tono que **gira con cada
   fotograma**. La zona arcoíris cambia de color mientras la simulación avanza.
3. **Cualquier otra cosa** (`turquesa`, `x`, `unicornio`): un tono vivo
   derivado del hash SHA-256 del nombre. Es estable (la misma palabra da
   siempre el mismo color, en todas las ejecuciones) y nunca falla.

Los códigos de escape los escribe **un único objeto**, `Painter`, que cierra
siempre con `RESET` (el color nunca se queda pegado al prompt). Si la terminal
anuncia truecolor (`COLORTERM=truecolor`) usa RGB de 24 bits; si no, busca el
más cercano de los 16 colores estándar. Con el color desactivado devuelve el
texto tal cual: el resto del código no necesita saber si hay color.

Los drones también tienen color propio: `Palette.drone_color(id)` reparte tonos con el
ángulo áureo (0,618 vueltas entre un id y el siguiente), así que dos drones
consecutivos nunca se parecen.

---

## 4. El mapa en la terminal

`MapLayout` coloca cada zona según sus **coordenadas del archivo**: la `x`
crece a la derecha y la `y` hacia arriba, como en un plano (en pantalla las
filas crecen hacia abajo, así que se invierte). La escala horizontal se ajusta
al ancho de la terminal; la vertical es de 3 filas por unidad, lo justo para
que quepa una etiqueta debajo de cada zona.

`Canvas` es una rejilla de celdas (carácter + color + negrita). Las conexiones
se trazan con Bresenham, eligiendo en cada paso `─`, `│`, `╱` o `╲` según la
dirección del paso. El orden de dibujo es deliberado:

1. **Conexiones**, en azul apagado; las usadas este turno, del color del dron
   que las usa.
2. **Drones en el aire**, como `◆` en el punto medio de su conexión.
3. **Zonas**, encima de todo: nunca las tapa un marcador.
4. **Etiquetas**, primero las de los hubs (son las que más importa leer) y
   después las demás, solo donde caben sin pisar nada. Si no caben enteras, se
   recortan con `…`.

Cada zona ocupa tres columnas y **su forma dice su tipo**, para que se lea
también sin color:

| Forma | Tipo | Centro |
|---|---|---|
| `( )` | normal | `·` vacía · `●` un dron (de su color) · `2`…`9`, `+` |
| `< >` | priority | igual |
| `[ ]` | restricted | igual |
| `▓▓▓` | blocked | — |
| `{ }` | start / end hub | igual |

Una zona **llena** pinta sus corchetes en rojo: el cuello de botella se ve sin
leer ningún número.

---

## 5. El HUD, pieza a pieza

Así se ve el turno 5 de `medium/02_circular_loop.txt` (sin color):

```
 ▌FLY-IN▐  02_circular_loop.txt                          TURN 005 / PAR 15  ·  W 8
 OUTPUT ▸ D1-goal D2-loop_b-exit_point D4-loop_b D6-loop_a

             (·)───────(·)
              │         │
              │         │
   {·}───────(2)───────(2)───◆───[·]───────{●}
  start    loop_a    loop_b   exit_poi…   goal

 DELIVERED █████░░░░░░░░░░░░░░░░░░░░░░░ 1/6   AIRBORNE 1   ON GROUND 4

 ┌ ZONES ──────────────────────────────────┐ ┌ EVENTS ──────────────────────────────────┐
 │ loop_a ■■ 2/2 FULL                      │ │ D1 ★ DELIVERED to goal                   │
 │ loop_b ■■ 2/2 FULL                      │ │ D2 ◆ takes off → exit_point (2 turns)    │
 │ goal     1 ∞ hub                        │ │ D4 → loop_b                              │
 │                                         │ │ D6 → loop_a                              │
 │                                         │ │ D1 ◆ lands on exit_point                 │
 │                                         │ │ D1 ◆ takes off → exit_point (2 turns)    │
 │                                         │ │ D3 → loop_b                              │
 └─────────────────────────────────────────┘ └──────────────────────────────────────────┘
```

Y cada elemento está ahí porque responde a una pregunta:

| Elemento | La pregunta que responde |
|---|---|
| **Barra superior**: mapa, turno, PAR, `W` | ¿Dónde estoy y cuánto llevo? En los mapas oficiales, **PAR** es el objetivo del subject |
| **`OUTPUT ▸`** | ¿Qué línea de `stdout` corresponde a esto? Une lo que se ve con lo que se entrega |
| **Mapa** | ¿Dónde está cada dron y por dónde puede ir? |
| **`◆` sobre una conexión** | ¿Quién está en el aire? Esos no ocupan zona |
| **`DELIVERED` / `AIRBORNE` / `ON GROUND`** | ¿Cuánto falta? La barra da sensación de progreso |
| **ZONES**: ocupación frente a capacidad, `FULL` en rojo | **¿Por qué espera alguien?** Es la pregunta clave del proyecto |
| **EVENTS**: despegues, aterrizajes, entregas; los antiguos, atenuados | ¿Qué acaba de pasar? |

En la captura se lee la historia entera del mapa sin saber nada del código:
`loop_a` y `loop_b` están llenas, D2 acaba de despegar hacia `exit_point` y
tardará dos turnos, D1 ya ha entregado, y el resto hace cola. Es exactamente
la explicación de los 15 turnos de la sección 6.3 de la narrativa de SP08.

Antes del primer turno hay una **pantalla de inicio**, con el logo en
degradado, el nombre del mapa, sus cifras y el PAR:

```
  ███████╗██╗  ██╗   ██╗      ██╗███╗   ██╗
  ██╔════╝██║  ╚██╗ ██╔╝      ██║████╗  ██║
  █████╗  ██║   ╚████╔╝ █████╗██║██╔██╗ ██║
  ██╔══╝  ██║    ╚██╔╝  ╚════╝██║██║╚██╗██║
  ██║     ███████╗██║         ██║██║ ╚████║
  ╚═╝     ╚══════╝╚═╝         ╚═╝╚═╝  ╚═══╝

  DRONE SWARM ROUTING SIMULATOR  ·  cooperative space-time A*

  MAP  02_circular_loop.txt
  INFO 7 zones · 7 links · 6 drones · WHCA* W=8
  PAR  15 turns

  ▶ LAUNCHING 6 DRONES …
```

Y al final, bajo el último fotograma, la **pantalla de misión completada**
(verde si se cumple el PAR, ámbar si no):

```
  ╔══════════════════════════════════════════════════╗
  ║   ★  MISSION COMPLETE  ★   15 TURNS   PAR 15 ✔   ║
  ╚══════════════════════════════════════════════════╝
  moves 30 · moves/turn 2.00 · avg delivery turn 10.0 · waits 30 · peak airborne 1 · 5 ms
  ✔ 6/6 drones delivered   ✔ capacities verified every turn
```

La segunda comprobación no es un adorno: `_verify` (SP08) recuenta zonas y
conexiones en **cada** turno, y si algo no cuadrara la simulación se habría
detenido antes de llegar a esta pantalla.

---

## 6. Tres modos, según dónde mires

| Situación | Modo | Qué se ve |
|---|---|---|
| `stderr` es una terminal | **En vivo** | Inicio, un fotograma por turno (borrando la pantalla), final |
| `stderr` va a un fichero o una tubería | **Registro** | Una cabecera y el resumen final, en texto plano |
| `-q` / `--quiet` | **Nada** | Solo las líneas de `stdout` |

El color se apaga con `--no-color`, con la variable `NO_COLOR` (una
convención muy extendida) y siempre que `stderr` no sea una terminal: los
códigos ANSI en un fichero son basura ilegible.

Durante la animación el cursor se oculta, y se devuelve en el `__exit__` de un
gestor de contexto: **también si la simulación falla o se pulsa Ctrl+C**. Hay
un test que fuerza un `SimulationError` en mitad de la animación y comprueba
que lo último que se escribe es el código que devuelve el cursor.

`--delay` fija los segundos por fotograma (0,4 por defecto; 0 para verlo de
golpe).

---

## 7. La repetición HTML (retirada)

La primera versión escribía también una repetición en un fichero HTML
(`--html`), y la segunda llevó esa animación al navegador en vivo. Las dos se
retiraron de la entrega: eran JavaScript, no Python, y no se podían defender
línea a línea en la evaluación. Su sitio lo ocupa la ventana pygame de la
[sección 11](#11-versión-final-la-ventana-pygame-y-el-log-en-la-terminal),
que conserva lo que funcionaba de ellas: la interpolación entre turnos, el
reparto en corona alrededor de las zonas, los drones en el aire a mitad de su
conexión, las conexiones iluminadas y la tarjeta final.

---

## 8. Lo que costó ajustar

Las primeras versiones funcionaban, pero no se leían bien:

- **El challenger a 80 columnas.** 24 unidades de ancho en 80 columnas dejan
  3 columnas por unidad: las zonas se tocan. Los nombres de los hubs salían
  recortados (`st…`, `im…`) porque las etiquetas de los vecinos ocupaban antes
  el hueco. Solución: los hubs se etiquetan primero y prueban tres
  alineaciones; los drones en el aire se dibujan antes que las zonas, para que
  nunca tapen un corchete.
- **El panel ZONES** cortaba `conv_restricted8` a `conv_restric`, y había
  tres iguales. Ahora el ancho del nombre se calcula con el espacio real del
  panel.

---

## 9. Cómo sabemos que funciona

La calidad visual se juzga a ojo, y eso se hizo con capturas reales de cada
vista. Los tests comprueban lo que no debe fallar **nunca**:

- `--no-color` no emite ni un código ANSI, en los 19 mapas.
- Cualquier `color=` se resuelve (`turquesa`, `#ff8800`, `rainbow`, `x`), y
  `rainbow` cambia con el fotograma.
- `Painter` siempre cierra con `RESET`; sin truecolor usa los 16 colores.
- Todas las zonas de los 19 mapas caen dentro del lienzo, y la orientación
  (x a la derecha, y hacia arriba) se respeta.
- El cursor se oculta una vez y se devuelve, también cuando la simulación
  falla.
- El fotograma contiene lo que importa (`1/1 FULL`, `DELIVERED`, la línea de
  `OUTPUT`, `PAR 10 ✔`), y un tránsito aparece como `◆ takes off`.
- El modo registro son cuatro líneas en texto plano.
- La grabación tiene un fotograma por turno más el inicial, con las
  posiciones correctas (tierra, aire, entregado).
- En la CLI, `stdout` sigue conteniendo solo las líneas de turno con la
  visualización activa.

---

## 10. Lo que este diseño no garantiza

- **Terminales estrechas.** Por debajo de ~80 columnas el mapa del
  challenger se comprime hasta que las zonas se tocan. La información sigue en
  los paneles, pero el mapa pierde legibilidad.
- **Anchura de algunos símbolos.** `★` y `◆` son de anchura "ambigua" en
  Unicode: en terminales configuradas para CJK ocupan dos columnas y
  desalinean los recuadros.

---

## 11. Versión final: la ventana pygame y el log en la terminal

### 11.1 De dónde viene

La visualización pasó por tres versiones:

1. **HUD de terminal + repetición HTML aparte** (secciones 2 a 10). El HUD
   sigue disponible como `make hud`.
2. **La animación en el navegador, en vivo**, con un servidor local que le
   enviaba cada turno. Se veía muy bien, pero eran unas 750 líneas de
   JavaScript, un servidor HTTP y varios hilos: código que no es Python y que
   no se podía defender en una corrección de Python con garantías.
3. **La versión final: una ventana pygame**, en el mismo proceso y el mismo
   hilo, con el log de eventos en la terminal. Todo el código entregado es
   Python.

La regla que decidió el cambio: *todo lo que se entrega tiene que poder
explicarse línea a línea*. La versión del navegador se conserva fuera del
repositorio, como pieza de presentación.

### 11.2 Simular primero, enseñar después

La simulación del challenger tarda 0,25 s; enseñarla, bastante más. Así que
primero se simula entero, con `ReplayRecorder` como observador (guarda dónde
está cada dron y la línea de `stdout` de cada turno), y después se **enseña**
lo grabado. `Session._play_log` recorre los turnos y en cada uno hace dos
cosas seguidas: escribe en la terminal el bloque del turno `k` y le pide a la
ventana que anime el turno `k` durante `--delay` segundos
(`PygameView.play_turn`). Como las dos cosas las hace el mismo bucle, van a la
par sin ninguna sincronización.

Grabar primero tiene otra ventaja: para animar un dron *entre* dos turnos hay
que saber de dónde sale y adónde llega, y la tarjeta final y la barra de
progreso necesitan saber cuántos turnos hay.

### 11.3 La escena: calcular una vez, dibujar muchas

La ventana dibuja 60 fotogramas por segundo. Todo lo que depende solo de la
simulación se calcula **una vez** en `Scene` (`scene.py`):

- `spots[k][dron]`: dónde va cada dron en cada turno. En una zona normal y
  solo, al centro; si comparte zona (o es un hub), en su hueco de un anillo
  alrededor; en el aire, en el punto medio de la conexión; entregado, en el
  objetivo.
- `used[k]`: qué conexiones se recorren de `k-1` a `k` y en qué sentido.
- `occupants`, `delivered`, `airborne` y los turnos con replanificación.

`scene.py` no importa pygame: se prueba sin pantalla.

### 11.4 El dibujo

`PygameView` dibuja cada fotograma por capas: fondo (un degradado radial y una
rejilla, precalculados), estrellas que titilan, conexiones, zonas, drones,
efectos, etiquetas, el HUD y, si toca, una tarjeta. Todo con primitivas de
`pygame.draw`; no hay imágenes.

- **Zonas** hexagonales con un halo de su color. La decoración cuenta el
  tipo: anillo ámbar a trazos que gira en las `restricted`, estrella dorada en
  las `priority`, cruz roja en las `blocked`, plataformas con una baliza que
  late en los hubs. Encima, **puntos de capacidad** que se llenan; la zona
  entera late en rojo al llenarse.
- **Drones** con forma de cuadricóptero, hélices que giran y estela. El que va
  hacia una `restricted` **se eleva**, proyecta una sombra y se queda sobre su
  conexión los dos turnos de vuelo.
- **Conexiones** con un flujo de luz que avanza en el sentido del viaje, del
  color del dron que las usa; las que llevan a una `restricted`, a trazos.
- **Efectos**: chispas y un "+1" en cada entrega, y un anillo rosa ("WHCA\*
  REPLAN") en cada replanificación.
- **HUD**: misión y PAR, el turno en grande, el anillo de entregados con los
  contadores, y la línea exacta de `stdout` del turno con la barra de
  progreso.
- **Tarjetas**: el *mission briefing* con la cuenta atrás 3-2-1-GO (la
  terminal cuenta a la vez) y la final, con los turnos, tres estrellas
  (entregados, sin violaciones, dentro del PAR) y las métricas.

![medium/02, turno 5: loop_a y loop_b llenas y D2 en el aire](./img/window_medium.png)

Tres piezas hacen que vaya fluido: `Glow` precalcula cada halo una sola vez
(círculos concéntricos que se suman al fondo), `Fonts` guarda los textos ya
dibujados (lo más caro de pygame) y `Scene` ya tiene los fotogramas.

![La tarjeta final](./img/window_complete.png)

### 11.5 Lo que salió al probarlo

- **El saludo de pygame.** Al importarse, pygame escribe una línea por
  **`stdout`**. Habría sido la primera línea de la salida del programa, y la
  corrección habría fallado. `Session` define `PYGAME_HIDE_SUPPORT_PROMPT`
  antes del import, y un test ejecuta el programa sin esa variable en el
  entorno para comprobar que `stdout` queda limpio.
- **pygame 2.6.1 en Python 3.14.** El módulo de fuentes viene roto, y el error
  es un `NotImplementedError`, no un `pygame.error`: habría tumbado el
  programa. Se cambió a **pygame-ce** (la edición comunitaria, mantenida
  activamente, con el mismo `import pygame`) y `open()` captura también ese
  error: si algo falla al abrir, la partida sigue en la terminal.
- **Revisión con capturas reales** (pygame dibuja en memoria con el driver
  `dummy` de SDL): las hélices de los drones pequeños parecían rayones (ahora
  son anillos con una pala que gira), las etiquetas del challenger se pegaban
  unas a otras (ahora dejan un margen), el halo detrás de los números grandes
  dejaba anillos visibles (se quitó) y la etiqueta START de hard/02 quedaba
  bajo el panel inferior (más margen abajo).

### 11.6 Nunca quedarse esperando

- `--view auto` solo abre la ventana con **terminal y pantalla gráfica**
  (`DISPLAY`/`WAYLAND_DISPLAY` en Linux). Con una tubería, en CI o en los
  tests, la vista es el log.
- Si pygame no está instalado o no puede abrir la ventana, se avisa y la
  partida sigue en la terminal.
- Si el usuario cierra la ventana (o pulsa `ESC`), desaparece en el acto y la
  terminal sigue sola.
- La tarjeta final espera una tecla, pero como mucho 20 s.

### 11.7 Cómo se prueba

`test/test_session.py` cubre la elección de vista, el log turno a turno, la
escena (sin pygame) y la ventana de verdad con el driver `dummy`: que dibuja
todos los turnos de los 19 mapas, que avanza a la par que el log, que cerrarla
no para la partida, que sin pygame o sin ventana se sigue en la terminal, que
la tarjeta final no espera para siempre, que el `with` cierra pygame y que
pygame no escribe nada en `stdout`.

## 12. Resumen: quién hace qué

| Pieza | Responsabilidad |
|---|---|
| `Simulator.run(observer)` | Avisar tras cada turno; descontar el tiempo del observador |
| `ReplayRecorder` | Posiciones y línea de `stdout` de cada turno |
| `Session` | Elegir vista; reproducir la partida en la ventana y en el log a la vez; caer a la terminal si no hay ventana |
| `Scene` | Los fotogramas precalculados, sin pygame |
| `PygameView` | La ventana: abrir, animar cada turno, tarjeta final, cerrar (context manager) |
| `Projection` / `Glow` / `Fonts` | Mapa a píxeles; halos precalculados; textos en caché |
| `EventLog` | El log de eventos de la terminal |
| `Palette` / `Painter` | Nombre → RGB (tabla, `#hex`, `rainbow`, hash); ANSI con `RESET` siempre, fallback a 16 colores |
| `MapLayout` / `Canvas` / `TerminalRenderer` | El HUD de terminal: mapa en caracteres, paneles y cursor devuelto siempre |
| `FlyIn` (`main.py`) | Elegir vista (`--view`), color y ritmo según terminal, pantalla, `--no-color`, `NO_COLOR`, `-q` y `--delay` |

Continúa en [`12-narrativa-sp11.md`](./12-narrativa-sp11.md): medir, ajustar y
entregar.
