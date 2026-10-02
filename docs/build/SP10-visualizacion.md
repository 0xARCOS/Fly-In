# SP10 — Visualización ✅

**Objetivo:** dar feedback visual de la simulación. **Es parte obligatoria**,
no bonus.

**Prerequisitos:** [SP09](./SP09-formato-salida.md) verde.

**Criterio de salida:** alguien que no ha leído tu código puede ver la ejecución
y entender qué pasa turno a turno.

---

## Paso 0 — Por qué esto no es opcional

El subject la lista dentro del **mandatory part** *(Cap. VII.1)*:

> *Visual Representation: Your implementation **must** provide visual feedback of
> the simulation, either through: colored terminal output showing drone movements
> and zone states / a graphical interface displaying the network and drone
> positions / both options.*

Y el Cap. VIII exige documentar *"the visual representation features and how they
enhance the user experience"* en el `README.md`. El Cap. VII.6 la incluye entre
los criterios de evaluación: *"Quality and usefulness of visual representation"*.

**El mínimo que cumple es la terminal a color.** La interfaz gráfica es
opcional. Empieza por la terminal y solo pasa a lo gráfico si el resto está
sólido.

## Paso 1 — Los colores del mapa existen para esto

El metadato `color=` del archivo de mapa no tiene ningún otro uso en el
proyecto: no afecta al pathfinding ni a la simulación. Su única razón de ser es
esta *(Cap. VI)*:

> *When colors are specified, the implementation should provide visual feedback
> through colored terminal output or graphical representation.*

⚠️ **No lo des por sentado — no hay lista fija de colores**
*(Cap. VI)*: *"Accepted values for `color` are any valid single-word string
(e.g., `red`, `blue`, `gray`). There is no fixed list of allowed colors."*

O sea que tu mapa puede traer `color=turquesa` o `color=#ff8800`. Tu renderer
necesita:

- una tabla de nombres conocidos → código ANSI,
- un **fallback sensato** para los desconocidos (el color por defecto del
  terminal, o un color derivado del hash del nombre),
- y **nunca** un crash por un color que no esperabas. Eso sería un proyecto no
  funcional *(Cap. III.1)* por un metadato decorativo.

## Paso 2 — Códigos ANSI, lo justo

No hace falta ninguna librería. Los códigos de escape son cadenas normales:

```python
RESET = "\033[0m"
COLORS = {
    "black": "\033[30m", "red": "\033[31m", "green": "\033[32m",
    "yellow": "\033[33m", "blue": "\033[34m", "magenta": "\033[35m",
    "cyan": "\033[36m", "white": "\033[37m", "gray": "\033[90m",
}
BOLD = "\033[1m"
```

Un texto coloreado es `f"{COLORS['red']}texto{RESET}"`.

⚠️ **No lo des por sentado — cierra SIEMPRE con `RESET`**
Si no lo haces, el color se queda pegado y el prompt del usuario sale rojo
después de ejecutar tu programa. Queda fatal y es trivial de evitar: una función
`paint(text, color)` que siempre añade el reset, y nunca escribir códigos a
mano fuera de ella.

⚠️ **No lo des por sentado — respeta las tuberías y `NO_COLOR`**
Los códigos ANSI en un fichero son basura ilegible. Desactiva el color cuando:

- la salida no es un terminal: `sys.stderr.isatty()` es `False`,
- la variable de entorno `NO_COLOR` está definida (es una convención
  ampliamente respetada).

Una sola bandera, comprobada en un único sitio: en Fly-In es
`FlyIn.make_painter`, y `Painter` es el único objeto que escribe códigos.

⚠️ **No lo des por sentado — la visualización va a `stderr`**
Repetido desde [SP09](./SP09-formato-salida.md) porque es donde más se olvida:
`stdout` contiene exclusivamente las líneas de turno del subject. Todo lo visual
va a `stderr`. Así `make run > salida.txt` deja un fichero limpio y el usuario
sigue viendo los colores en pantalla.

## Paso 3 — Qué mostrar en cada turno

La pregunta que responde el criterio de salida: *¿qué necesita ver alguien para
entender qué está pasando?*

```
╭─ Turno 4 ──────────────────────────────────────────╮
│  start    [∞]   ·                                  │
│  narrow   [1]   D3                    ← cuello     │
│  roofA    [2]   D1 D5                              │
│  tunnelB  [1]   ·          (blocked)               │
│  goal     [∞]   D2 D4                  entregados  │
╰────────────────────────────────────────────────────╯
   En vuelo:  D6 → hub-roof1  (llega el turno 5)
   Entregados: 2/6
```

Los elementos que aportan de verdad:

| Elemento | Por qué |
|---|---|
| Número de turno | Ancla todo lo demás |
| Cada zona con su capacidad y sus ocupantes | Es la regla que más se viola; verlo hace obvio si funciona |
| Color por tipo de zona (o por `color=`) | Identificar `blocked`/`restricted` de un vistazo |
| Drones en tránsito, aparte | Están "en el aire": no pertenecen a ninguna zona |
| Contador de entregados | Da sensación de progreso |
| Marcar las zonas al **límite** de capacidad | Enseña dónde está el cuello de botella real |

⚠️ **No lo des por sentado — muestra la capacidad, no solo la ocupación**
`narrow: D3` no dice nada. `narrow [1]: D3` dice que está **llena** y que
cualquier otro dron tendrá que esperar. Es la diferencia entre una lista de
posiciones y una explicación de por qué la simulación hace lo que hace — que es
literalmente lo que pide el criterio de salida.

## Paso 4 — Las piezas

En Fly-In la visualización **no se dibuja mientras se simula**: primero se
simula entero (milisegundos) y después se enseña lo grabado al ritmo de
`--delay`. Las piezas, en `fly_in/visualization/`:

| Pieza | Qué hace |
|---|---|
| `ReplayRecorder` (`recorder.py`) | Observador del simulador: en cada `on_turn` guarda dónde está cada dron y la línea de `stdout` del turno |
| `EventLog` (`event_log.py`) | El log de la terminal: un bloque por turno con la línea de `stdout`, las replanificaciones, cada movimiento, quién espera y qué zona se acaba de llenar |
| `Scene` (`scene.py`) | Los fotogramas de la ventana, precalculados una vez y sin pygame |
| `PygameView` (`pygame_view.py`) | La ventana: abrir, animar un turno, pausar con `SPACE`, tarjeta final, cerrar |
| `Session` (`session.py`) | Elige la vista y reproduce la partida en la ventana y en el log a la vez |
| `Palette` / `Painter` (`palette.py`) | Nombre de color → RGB; RGB → código ANSI con `RESET` siempre |

El punto de enganche con el simulador es uno solo:

```python
class SimulationObserver(Protocol):
    def on_turn(
        self, turn: int, moves: Sequence[Move], drones: Sequence[Drone]
    ) -> None: ...
```

⚠️ **No lo des por sentado — la visualización NO calcula nada**
Recibe el estado y lo dibuja. Si empieza a deducir ocupaciones o a recorrer
rutas, has duplicado lógica del simulador en la capa de presentación, y algún
día divergirán: verás una cosa en pantalla y otra en la salida. Lee; no piensa.

## Paso 5 — La vista gráfica

Las coordenadas `x`/`y` de las zonas existen exactamente para esto: son las
posiciones de los nodos en el dibujo.

| Opción | Ventaja | Inconveniente |
|---|---|---|
| `matplotlib` | Fácil de exportar a PNG/GIF | Animación tosca |
| **`pygame-ce`** (la elegida) | Animación fluida, control total, el mismo `import pygame` | Una dependencia, más código |
| SVG generado a mano | Cero dependencias | Sin animación real |

⚠️ **Debe ser opcional en tiempo de ejecución.** `pygame-ce` está en
`dependencies` de `pyproject.toml`, pero se importa **dentro** de
`Session._play_window`, con `try/except ImportError`: si falta, o si no puede
abrir la ventana, el programa sigue en la terminal con un aviso.

---

## Tests de cierre

La visualización es difícil de testear y tampoco tiene mucho sentido hacerlo a
fondo. Lo mínimo que sí conviene:

- [x] Sin color (`NO_COLOR` o tubería) no se emite ningún código ANSI
- [x] Un `color=` desconocido no lanza excepción
- [x] Nada de lo que emite la visualización aparece en `stdout`
- [x] Un mapa sin ningún `color=` se renderiza correctamente

Lo demás se valida a ojo, que es exactamente el criterio de salida.

---

## Criterio de salida

- [x] Ejecutas `bottleneck.txt` y **se ve** por qué los drones se turnan
- [x] Los colores del mapa se reflejan en pantalla
- [x] `NO_COLOR` y las tuberías dan salida limpia
- [x] `stdout` sigue conteniendo solo las líneas de turno
- [x] Una captura guardada para el `README.md`

## Decisiones a anotar

- Qué muestra tu vista y **por qué cada elemento ayuda** — el subject pide
  documentar *cómo mejora la experiencia*, no solo que existe *(Cap. VIII)*
- ¿Terminal, gráfico o ambos? Y si hay gráfico, cómo se degrada sin la librería
- Cómo resuelves los colores desconocidos

## Decisiones tomadas

Implementado en `fly_in/visualization/` (`palette.py`, `recorder.py`,
`scene.py`, `pygame_view.py`, `event_log.py` y `session.py`), probado en `test/test_visualization.py` y
`test/test_session.py`. La historia completa, con capturas,
está en [`11-narrativa-sp10.md`](../11-narrativa-sp10.md).

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| **Por defecto, ventana pygame + terminal a la vez** (`--view auto` → `window`): la animación en la ventana y el log de eventos en la terminal, turno a turno | La animación en el navegador (segunda versión: servidor local + JavaScript) | Todo el código entregado es Python y se puede defender línea a línea. La versión del navegador se conserva fuera del repositorio |
| **pygame-ce** en `dependencies`, importado de forma perezosa dentro de `Session._play_window` | pygame 2.6.1; import al principio del módulo | pygame 2.6.1 trae las fuentes rotas en Python 3.14. Con el import perezoso, sin pygame todo lo demás funciona y la ventana cae a la terminal |
| Un solo hilo: se escribe el bloque del turno `k` y se anima el turno `k` | Hilos o un proceso aparte | pygame exige manejar la ventana desde el hilo que la crea, y con un bucle no hay condiciones de carrera |
| `PYGAME_HIDE_SUPPORT_PROMPT` antes del import | — | pygame saluda por `stdout` al importarse: rompería la salida del subject |
| Simular primero y **enseñar después** a ritmo de `--delay` (`Session.play`) | Animar mientras se simula | La simulación dura milisegundos; así el ritmo lo marca solo la presentación, igual para las dos pantallas |
| `auto` elige la ventana solo con terminal **y** pantalla gráfica; si pygame falla o se cierra la ventana, sigue solo en la terminal | Intentar abrirla siempre | Nunca colgarse ni fallar (Cap. III.1): tuberías, CI y tests usan el log |
| `Scene` precalcula los fotogramas y no importa pygame | Calcular posiciones en cada fotograma | La ventana dibuja a 60 fps; así el bucle solo consulta listas, y la escena se prueba sin pantalla |
| Sin HUD de terminal | Un HUD a pantalla completa como tercera vista (se llegó a hacer) | La hoja pide terminal a color **o** gráfico; la ventana y el log ya lo cubren y el HUD era código que defender sin que nadie lo pidiera |
| La grabación es un **observador** del simulador (`on_turn`) | Que el simulador llame a `print` | El simulador no sabe nada de pantallas; el observador solo lee drones y `Move`. El tiempo que pasa dentro del observador se descuenta del tiempo de cálculo |
| Mapa dibujado con las coordenadas `x`/`y` del archivo, una escala por eje ajustada a la ventana | Lista de zonas | La lista del paso 3 no enseña la topología; el mapa sí, y las coordenadas existen para esto |
| Colores: tabla de nombres → RGB, `#rrggbb`, `rainbow` animado y tono derivado de un hash para lo desconocido | Color por defecto para lo desconocido | Nunca falla y dos zonas con el mismo color raro se ven iguales. Truecolor si `COLORTERM` lo anuncia; si no, el más cercano de 16 |
| Tres niveles: ventana + log (terminal con pantalla), log solo (sin pantalla; sin pausas ni color si no hay terminal) y nada (`-q`) | Siempre animar | Los códigos ANSI en un fichero son basura; `NO_COLOR` quita el color incluso en terminal |
| La cabecera de cada turno del log repite su línea de `stdout` | — | Une lo que se ve con lo que se entrega |
| PAR en los mapas oficiales (briefing y tarjeta final) | — | El objetivo del subject convierte la tarjeta final en un "¿lo he conseguido?" (`OVER PAR` si no) |
| `SPACE` pausa; sin navegación por turnos | Flechas para ir y venir entre turnos | La navegación se probó y se retiró: no llegó a funcionar y el log ya da el detalle de cada turno |
