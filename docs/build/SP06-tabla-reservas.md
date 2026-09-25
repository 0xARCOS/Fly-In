# SP06 — `ReservationTable`: la ocupación espacio-temporal ⬜

**Objetivo:** llevar el registro de qué está ocupado, **en qué turno**, y por
cuántos drones — para que la búsqueda de un dron pueda esquivar a los que
planificaron antes que él.

**Prerequisitos:** [SP01](./SP01-modelo-dominio.md) verde. *(No necesita
pathfinding: puedes hacerlo en paralelo a SP04/SP05.)*

**Criterio de salida:** las capacidades se respetan, `start_hub`/`end_hub` nunca
bloquean, un tránsito `restricted` ocupa la conexión dos turnos, y `clear_from`
borra exactamente lo que debe.

---

## Paso 1 — Las tres cosas distintas que se reservan

Confundirlas es **el bug clásico** de este subproyecto.

| Reserva | Clave | Existe para |
|---|---|---|
| **Ocupación de zona** | `(nombre_zona, turno)` → nº de drones | Respetar `max_drones` |
| **Ocupación de conexión** | `(nombre_conexión, turno)` → nº de drones | Respetar `max_link_capacity`, y bloquear el enlace durante los 2 turnos de una `restricted` |
| **Movimiento direccional** | `(origen, destino, turno)` | Evitar que A→B y B→A se crucen por el mismo enlace en el mismo turno |

⚠️ **No lo des por sentado — por qué el cruce necesita una estructura aparte**
Imagina una conexión con `max_link_capacity=2`. Dron 1 va de `a` a `b`; dron 2
va de `b` a `a`, en el mismo turno. Numéricamente la capacidad lo permite: son
2 drones y caben 2. **Físicamente es imposible**: se atravesarían.

Es el *edge conflict* de la literatura MAPF, y no se detecta contando drones:
hace falta saber **en qué dirección** va cada uno. De ahí la tercera estructura.

El subject no menciona explícitamente esta regla, así que es una **decisión de
diseño tuya**: decides que tu simulación es físicamente coherente. Anótala y
defiéndela en la review — es el tipo de detalle que demuestra que has pensado el
problema y no solo lo has codificado.

## Paso 2 — La regla que más tiempo ahorra

⚠️ **`start_hub` y `end_hub` NUNCA se reservan.**

*(Cap. VII.2)*: ambas tienen capacidad ilimitada. Todos los drones empiezan en
`start_hub` y cualquier número puede llegar a `end_hub`.

Si tu tabla las trata como zonas normales de capacidad 1, con 5 drones el cuarto
no podrá ni salir de casa. Y el síntoma que verás **no** será *"start_hub
llena"*: será *"el dron 4 no encuentra ruta"*, y te pasarás la tarde depurando
la búsqueda de SP07, que está perfectamente bien.

**Ya está resuelto en el modelo, no lo dupliques.** El parser da a
`start_hub`/`end_hub` `max_drones = UNLIMITED` (`float("inf")`, en
`fly_in/models/zone.py`). Así la comprobación genérica ya es cierta para ellas,
sin ningún `if` especial:

```python
def zone_has_room(self, zone: Zone, turn: int) -> bool:
    return self._zones.get((zone.name, turn), 0) < zone.max_drones
```

No añadas además un `if zone is graph.start_hub`: dos mecanismos para la misma
regla acaban divergiendo. El test "reservar `start_hub` con 100 drones nunca
falla" es el que te protege si alguien cambia el parser.

Para obtener la `Connection` de un movimiento `frm → to`, usa
`graph.connection_between(frm, to)` (O(1), funciona en ambos sentidos).

## Paso 3 — La interfaz

`fly_in/pathfinding/reservation_table.py`

```python
class ReservationTable:
    """Ocupación espacio-temporal de zonas y conexiones.

    Las zonas start_hub y end_hub tienen capacidad ilimitada (Cap. VII.2) y
    nunca se consideran ocupadas.
    """

    def __init__(self, graph: Graph) -> None:
        self._graph = graph
        self._zones: dict[tuple[str, int], int] = {}
        self._links: dict[tuple[str, int], int] = {}
        self._moves: set[tuple[str, str, int]] = set()

    # --- consultas -----------------------------------------------------
    def zone_has_room(self, zone: Zone, turn: int) -> bool:
        """¿Cabe un dron más en `zone` durante `turn`?"""

    def link_has_room(self, conn: Connection, turn: int) -> bool:
        """¿Cabe un dron más en la conexión durante `turn`?"""

    def would_swap(self, frm: Zone, to: Zone, turn: int) -> bool:
        """¿Hay ya un dron haciendo el movimiento inverso en ese turno?"""

    # --- escritura -----------------------------------------------------
    def reserve_move(self, frm: Zone, to: Zone, conn: Connection,
                     turn: int, cost: int) -> None:
        """Reserva un movimiento que empieza en `turn` y dura `cost` turnos.

        Ocupa la conexión durante los `cost` turnos del trayecto y la zona
        destino a partir de la llegada (turn + cost).
        """

    def reserve_wait(self, zone: Zone, turn: int) -> None:
        """Reserva la permanencia de un dron en `zone` durante `turn`."""

    def clear_from(self, turn: int) -> None:
        """Descarta todas las reservas de `turn` en adelante.

        Las reservas anteriores a `turn` son historia ya ejecutada y se
        conservan intactas.
        """
```

### Convención de tiempo (compartida con SP07 y SP08)

- `_zones[(z, t)]` cuenta los drones que **están en `z` durante el turno
  `t`**, es decir, los que esperan ahí en `t`. Un dron que *sale* de `z` en el
  turno `t` ya no cuenta en `(z, t)`: así se cumple "drones moving out of a
  zone free up capacity for that same turn" (Cap. VII.3) sin código extra.
- Un movimiento que empieza en el turno `T` con coste `c` ocupa la conexión en
  `T … T+c-1` y la zona destino desde `T+c` (tabla del paso 4).
- La salida (SP09) imprime el movimiento en la línea del turno en que
  **termina**: `T` para coste 1; `T` (conexión) y `T+1` (zona) para coste 2.
- Por tanto, al comprobar si un dron puede entrar en `destino` saliendo en
  `T`, la pregunta correcta es `zone_has_room(destino, T + cost)`.

SP07 y SP08 deben usar exactamente esta convención. Un desfase de ±1 aquí se
ve como "drones que chocan un turno sí y otro no", y es muy difícil de
rastrear desde arriba.

## Paso 4 — `reserve_move()`: el caso `restricted` con cuidado

Un dron que entra en el turno `T` en una conexión hacia una zona `restricted`
(coste 2):

| Turno | Ocupa la conexión | Ocupa una zona |
|---|---|---|
| `T` | ✅ | ❌ (ya salió de la de origen) |
| `T+1` | ✅ | ❌ **está en el aire** |
| `T+2` en adelante | ❌ | ✅ la zona destino |

Y con coste 1 (zona `normal`/`priority`), el mismo método debe dar:

| Turno | Ocupa la conexión | Ocupa una zona |
|---|---|---|
| `T` | ✅ | ❌ |
| `T+1` en adelante | ❌ | ✅ la zona destino |

⚠️ **No lo des por sentado — no asumas "coste 1 = una casilla de tiempo"**
Escribe `reserve_move` recibiendo el `cost` y reservando el **rango completo**
`range(turn, turn + cost)` para la conexión, y la zona destino desde
`turn + cost`. Si haces dos métodos distintos, uno para movimientos normales y
otro para restringidos, tendrás la misma lógica duplicada y divergirán.

⚠️ **No lo des por sentado — el dron en tránsito no ocupa NINGUNA zona**
*(Cap. VII.3)*. En `T+1` está literalmente en el aire. Si por comodidad lo
dejas "ocupando" la zona de origen durante el tránsito, estás bloqueando una
zona que en realidad está libre, y otro dron que podría haber pasado por ahí se
quedará esperando sin motivo. Tu recuento de turnos subirá y no sabrás por qué.

### Hasta cuándo se reserva la zona destino

Aquí hay una decisión real que tomar. Un dron que llega a una zona en el turno
`T+cost` se queda ahí **hasta que se mueve otra vez**, lo cual puede ser mucho
después. Dos opciones:

| Opción | Cómo | Contra |
|---|---|---|
| Reservar solo el turno de llegada, y que cada turno de espera posterior se reserve con `reserve_wait` | La ruta completa se graba turno a turno | Requiere que quien graba la ruta recorra todos los turnos, incluidos los de espera |
| Reservar un rango hasta la siguiente salida | Una llamada por tramo | Requiere conocer la salida al grabar |

**Recomendación: la primera.** Grabar la ruta turno a turno (incluidas las
esperas) mantiene `reserve_move` simple y hace que la tabla sea una foto exacta
de "dónde está cada dron en cada turno". La segunda parece más eficiente pero
mezcla dos decisiones en una llamada.

Sea cual sea, **escríbela en `## Decisiones tomadas`**: es justo lo que un
evaluador pregunta cuando ve la tabla.

## Paso 5 — `clear_from()` y la ventana

Al replanificar en el turno `T` ([SP07](./SP07-whca.md)), las reservas a partir
de `T` son **predicciones obsoletas** y hay que tirarlas; las anteriores a `T`
son historia ya ejecutada y se conservan.

```python
def clear_from(self, turn: int) -> None:
    self._zones = {k: v for k, v in self._zones.items() if k[1] < turn}
    self._links = {k: v for k, v in self._links.items() if k[1] < turn}
    self._moves = {m for m in self._moves if m[2] < turn}
```

⚠️ **No lo des por sentado — es `< turn`, estrictamente**
Las reservas **del propio turno `T`** también se descartan: son parte de lo que
vas a replanificar. Si usas `<=`, conservarás las reservas del turno actual
mientras planificas ese mismo turno, y los drones chocarán consigo mismos —
literalmente: la búsqueda del dron 1 verá la reserva del dron 1 y la esquivará.

⚠️ **No lo des por sentado — no mutes el diccionario mientras lo recorres**
`for k in self._zones: if ...: del self._zones[k]` lanza
`RuntimeError: dictionary changed size during iteration`. Construye uno nuevo
por comprensión, como arriba, o itera sobre `list(self._zones.items())`.

---

## Tests de cierre (`test/test_reservation_table.py`)

- [ ] Dos drones no pueden reservar la misma zona de `max_drones=1` en el mismo turno
- [ ] Tres drones **sí** pueden reservar una zona de `max_drones=3`
- [ ] El mismo dron en turnos distintos no interfiere consigo mismo
- [ ] Reservar `start_hub` nunca falla, con 100 drones
- [ ] Reservar `end_hub` nunca falla, con 100 drones
- [ ] `max_link_capacity` se respeta en una conexión
- [ ] Un movimiento de coste 2 ocupa la conexión en `T` y `T+1`, y la zona destino desde `T+2`
- [ ] Un movimiento de coste 2 **no** ocupa ninguna zona en `T+1`
- [ ] `would_swap` detecta A→B contra B→A en el mismo turno
- [ ] `would_swap` es `False` si los movimientos van en turnos distintos
- [ ] `clear_from(5)` deja intactas las reservas de los turnos 0–4 y borra las de 5 en adelante

---

## Criterio de salida

- [ ] Los 11 tests pasan
- [ ] Ninguna comprobación explícita de "es start/end hub": la capacidad
      `UNLIMITED` del modelo lo resuelve
- [ ] `make lint-strict` pasa

## Decisiones a anotar

- ¿Hasta cuándo se reserva una zona tras la llegada? *(Ver paso 4.)*
- ¿Implementas la regla anti-cruce, sabiendo que el subject no la exige? *(La
  guía dice que sí, por coherencia física. Justifícalo.)*
- ¿Guardas **quién** reservó (ID del dron) o solo el recuento? *(El recuento
  basta para la lógica; guardar el ID cuesta poco y hace la depuración y la
  visualización muchísimo más fáciles. Recomendado.)*
