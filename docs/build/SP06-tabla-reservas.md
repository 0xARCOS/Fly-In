# SP06 — `ReservationTable`: la ocupación espacio-temporal ✅

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
| **Movimiento direccional** | `(origen, destino, turno)`, uno por cada turno del trayecto | Evitar que A→B y B→A se crucen por el mismo enlace en el mismo turno (también en el segundo turno de un tránsito `restricted`) |

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

`fly_in/pathfinding/reservation_table.py` (implementado)

```python
class ReservationTable:
    def __init__(self, graph: Graph) -> None: ...

    # --- consultas -----------------------------------------------------
    def zone_has_room(self, zone: Zone, turn: int) -> bool: ...
    def link_has_room(self, conn: Connection, turn: int) -> bool: ...
    def would_swap(self, frm: Zone, to: Zone, turn: int) -> bool: ...
    def can_move(self, frm: Zone, to: Zone, turn: int) -> bool: ...
    def zone_occupants(self, zone: Zone, turn: int) -> list[int]: ...
    def link_occupants(self, conn: Connection, turn: int) -> list[int]: ...

    # --- escritura -----------------------------------------------------
    def reserve_move(self, drone_id: int, frm: Zone, to: Zone,
                     turn: int) -> None: ...
    def reserve_wait(self, drone_id: int, zone: Zone, turn: int) -> None: ...
    def clear_from(self, turn: int,
                   keep: AbstractSet[int] = frozenset()) -> None: ...
```

Diferencias con el borrador original, y por qué:

| Cambio | Por qué |
|---|---|
| `reserve_move` ya no recibe `conn` ni `cost` | La tabla los deduce con `graph.connection_between()` y `to.movement_cost()`. Pasarlos desde fuera permitía incoherencias (p. ej. coste 1 hacia una `restricted`) que nadie detectaría |
| Nuevo `can_move()` | Una sola pregunta comprueba **todo** lo que ocupa un movimiento: la conexión y el sentido en cada turno del trayecto, y la zona de llegada. SP07 ya no puede olvidarse de una de las tres comprobaciones |
| Todas las escrituras reciben `drone_id` | La tabla guarda **quién** ocupa cada casilla, no solo cuántos. Hace falta para `clear_from(keep=...)` y para depurar |
| `reserve_*` lanza `ReservationError` si no cabe, y es atómico | Reservar algo que no cabe es siempre un bug del planificador: mejor que falle aquí, sin dejar la tabla a medias |
| `clear_from` acepta `keep` | Para no borrar la llegada comprometida de los drones en el aire (ver paso 5) |

### Convención de tiempo (compartida con SP07 y SP08)

- El **instante `t`** es el estado tras ejecutar `t` turnos. El instante 0 es
  el inicial: todos los drones en `start_hub`. La línea `k` de la salida es el
  paso del instante `k-1` al instante `k`.
- **Zona `(z, t)`**: drones que están en `z` en el instante `t`.
- **Conexión `(c, t)`**: drones que están cruzando `c` entre el instante `t`
  y el `t+1`.
- Un movimiento que sale de `frm` en el instante `T` con coste `c` ocupa la
  conexión en `T … T+c-1` y la zona destino en el instante `T+c`. En los
  instantes intermedios no ocupa ninguna zona.
- "Los drones que salen liberan capacidad en ese mismo turno" (Cap. VII.3) se
  cumple solo: un dron que sale de `z` en `T` está en `(z, T)` pero no en
  `(z, T+1)`, que es justo donde se comprueba la llegada del que entra.
- En la salida (SP09), un movimiento que sale en `T` se imprime en la línea
  `T+1`; un tránsito `restricted` imprime la conexión en `T+1` y la zona en
  `T+2`.

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
`reserve_move` reserva el **rango completo** `range(turn, turn + cost)` para
la conexión (y el sentido), y la zona destino en `turn + cost`, con `cost`
deducido de la zona destino. Si haces dos métodos distintos, uno para movimientos normales y
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

Implementado con un único helper, `_filtered()`, que construye un diccionario
nuevo con las reservas `< turn` más las de los drones de `keep`. El mismo
helper sirve a `release(drone_id, turn)`, que borra solo las reservas de un
dron de `turn` en adelante: [SP07](./SP07-whca.md#resuelto-en-plan-la-reserva-provisional)
lo usa para cambiar la reserva provisional de un dron por su ruta real.

⚠️ **No lo des por sentado — los drones en el aire se conservan con `keep`**
Un dron que salió hacia una `restricted` en `T-1` sigue en la conexión en `T`
y aterriza en `T+1`. Si `clear_from(T)` borrara esas dos reservas, otro dron
podría ocupar la conexión o la zona de aterrizaje, y el primero no tendría
dónde llegar: el subject prohíbe esperar en el aire. SP08 llama a
`clear_from(T, keep={ids de drones IN_TRANSIT})` y no los replanifica en ese
ciclo: su plan anterior sigue reservado y los demás lo esquivan.

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

## Tests de cierre (`test/test_reservation_table.py`, 27 tests)

- [x] Dos drones no pueden reservar la misma zona de `max_drones=1` en el mismo turno
- [x] Tres drones **sí** pueden reservar una zona de `max_drones=3`
- [x] El mismo dron en turnos distintos no interfiere consigo mismo
- [x] Reservar `start_hub` nunca falla, con 100 drones
- [x] Reservar `end_hub` nunca falla, con 100 drones
- [x] `max_link_capacity` se respeta en una conexión (también hacia `end_hub`)
- [x] Un movimiento de coste 2 ocupa la conexión en `T` y `T+1`, y la zona destino en `T+2`
- [x] Un movimiento de coste 2 **no** ocupa ninguna zona en `T+1`
- [x] `would_swap` detecta A→B contra B→A en el mismo turno
- [x] `would_swap` es `False` si los movimientos van en turnos distintos
- [x] `clear_from(5)` deja intactas las reservas de los turnos 0–4 y borra las de 5 en adelante
- [x] Extra: salir de una zona la libera para el que entra en ese mismo turno
- [x] Extra: la conexión `restricted` sigue ocupada en el segundo turno del tránsito
- [x] Extra: el cruce se detecta también en el segundo turno de un tránsito `restricted`
- [x] Extra: una reserva fallida no deja nada a medias
- [x] Extra: `clear_from(keep=...)` conserva a los drones en el aire
- [x] Extra: un mismo dron no se puede contar dos veces en la misma casilla

---

## Criterio de salida

- [x] Todos los tests pasan
- [x] Ninguna comprobación explícita de "es start/end hub": la capacidad
      `UNLIMITED` del modelo lo resuelve
- [x] `make lint-strict` pasa

## Decisiones tomadas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| La zona destino se reserva solo en el instante de llegada; cada espera posterior es un `reserve_wait` | Reservar un rango hasta la siguiente salida | La tabla es una foto exacta de dónde está cada dron en cada instante, y `reserve_move` no necesita conocer el futuro |
| Anti-cruce activado (`would_swap`) en cada turno del trayecto | No comprobar el sentido | Dos drones cruzándose en la misma conexión es físicamente imposible aunque la capacidad numérica lo permita. El subject no lo exige, pero tampoco lo permite explícitamente: elegimos la simulación coherente |
| Conexión `restricted` ocupada los dos turnos del tránsito | Contarla solo el turno de salida | Cap. VII.3: *"the drone occupies the connection during transit"*. Cuesta algún turno en mapas con enlaces `restricted` de capacidad 1, pero es la lectura literal |
| Se guarda el id del dron, no solo el recuento | `dict[clave, int]` | Imprescindible para `clear_from(keep=...)`; además permite ver quién ocupa qué al depurar |
| Claves por nombre (`str`), no por objeto `Zone` | Claves `(Zone, int)` | `Zone` hashea por identidad: funciona, pero una clave legible hace los volcados de depuración comprensibles, y los nombres son únicos por construcción |
| `ReservationError` en vez de devolver `False` al reservar | `reserve_*` devuelve `bool` | Un `bool` se puede ignorar sin querer; una excepción no. Quien quiera preguntar usa `can_move` / `zone_has_room` |
