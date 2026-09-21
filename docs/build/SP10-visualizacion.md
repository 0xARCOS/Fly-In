# SP10 — Visualización ⬜

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

⚠️ **No lo des por sentado — respeta `--no-color` y las tuberías**
Los códigos ANSI en un fichero son basura ilegible. Desactiva el color cuando:

- el usuario pasa `--no-color` ([SP03](./SP03-cli-y-errores.md)),
- la salida no es un terminal: `sys.stderr.isatty()` es `False`,
- la variable de entorno `NO_COLOR` está definida (es una convención
  ampliamente respetada).

Una sola bandera en el renderer, comprobada en `paint()`.

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

## Paso 4 — La clase

`fly_in/visualization/terminal_view.py` (crea la carpeta y su `__init__.py`)

```python
class TerminalRenderer:
    """Dibuja el estado de la simulación en la terminal, con color ANSI.

    Escribe siempre en stderr: stdout está reservado al formato de salida
    del subject (Cap. VII.5).
    """

    def __init__(self, graph: Graph, use_color: bool = True) -> None: ...

    def render_turn(self, turn: int, drones: list[Drone]) -> None:
        """Dibuja el estado completo tras aplicar el turno `turn`."""

    def render_summary(self, turns: int, drones: list[Drone]) -> None:
        """Resumen final: turnos totales y métricas secundarias."""
```

⚠️ **No lo des por sentado — el renderer NO calcula nada**
Recibe el estado y lo dibuja. Si empieza a deducir ocupaciones o a recorrer
rutas, has duplicado lógica del simulador en la capa de presentación, y algún
día divergirán: verás una cosa en pantalla y otra en la salida. El renderer lee;
no piensa.

## Paso 5 — Opcional: la vista gráfica

Solo si el mandatory está sólido. Las coordenadas `x`/`y` de las zonas existen
exactamente para esto: son las posiciones de los nodos en el dibujo.

| Opción | Ventaja | Inconveniente |
|---|---|---|
| `matplotlib` | Probablemente ya instalado; fácil de exportar a PNG/GIF para el README | Animación tosca |
| `pygame` | Animación fluida, control total | Una dependencia más, más código |
| SVG generado a mano | Cero dependencias, se ve en cualquier navegador y se incrusta en el README | Sin animación real (o un frame por turno) |

⚠️ **Sea cual sea, debe ser opcional en tiempo de ejecución.** Si `pygame` no
está instalado, el programa debe seguir funcionando con la terminal, no
reventar en el `import`. Usa un import perezoso dentro de la función, con
`try/except ImportError` y un aviso claro.

Y recuerda: `dependencies = []` en `pyproject.toml` hoy. Cualquier librería
gráfica va en un extra aparte (`[project.optional-dependencies].viz`), nunca en
las dependencias obligatorias — si no, `make install` falla en una máquina sin
entorno gráfico y el proyecto entero deja de arrancar.

---

## Tests de cierre

La visualización es difícil de testear y tampoco tiene mucho sentido hacerlo a
fondo. Lo mínimo que sí conviene:

- [ ] `--no-color` no emite ningún código ANSI
- [ ] Un `color=` desconocido no lanza excepción
- [ ] Nada de lo que emite el renderer aparece en `stdout`
- [ ] Un mapa sin ningún `color=` se renderiza correctamente

Lo demás se valida a ojo, que es exactamente el criterio de salida.

---

## Criterio de salida

- [ ] Ejecutas `bottleneck.txt` y **se ve** por qué los drones se turnan
- [ ] Los colores del mapa se reflejan en pantalla
- [ ] `--no-color` y las tuberías dan salida limpia
- [ ] `stdout` sigue conteniendo solo las líneas de turno
- [ ] Una captura guardada para el `README.md`

## Decisiones a anotar

- Qué muestra tu vista y **por qué cada elemento ayuda** — el subject pide
  documentar *cómo mejora la experiencia*, no solo que existe *(Cap. VIII)*
- ¿Terminal, gráfico o ambos? Y si hay gráfico, cómo se degrada sin la librería
- Cómo resuelves los colores desconocidos
