# SP08 — `Drone` y `Simulator`: el bucle turno a turno ✅

**Objetivo:** ejecutar la simulación: avanzar turno a turno, mover los drones,
replanificar cada `W/2` turnos, y terminar cuando todos han llegado.

**Prerequisitos:** [SP07](./SP07-whca.md) y [SP03](./SP03-cli-y-errores.md)
verdes.

**Criterio de salida:** todos los drones llegan; ninguna regla de ocupación se
viola en ningún turno; el resultado **no depende del orden de la lista de
drones**.

---

## Paso 0 — Crear el paquete

```console
$ mkdir -p fly_in/simulation && touch fly_in/simulation/__init__.py
```

## Paso 1 — `Drone` y `DroneState`

`fly_in/simulation/drone.py`

```python
class DroneState(Enum):
    WAITING = auto()      # en una zona, sin movimiento este turno
    MOVING = auto()       # se mueve a una zona adyacente este turno
    IN_TRANSIT = auto()   # en una conexión hacia una restricted, llega el turno que viene
    ARRIVED = auto()      # en end_hub: entregado, deja de rastrearse


class Drone:
    """Un agente que recorre el grafo de start_hub a end_hub."""

    def __init__(self, drone_id: int, start: Zone) -> None:
        self.id = drone_id
        self.current_zone = start
        self.state = DroneState.WAITING
        self.path: list[Step] = []
        self.transit_connection: Optional[Connection] = None
        self.transit_turns_left = 0
```

```mermaid
stateDiagram-v2
    [*] --> WAITING: creado en start_hub
    WAITING --> MOVING: tiene siguiente paso hacia zona normal/priority
    MOVING --> WAITING: llegó, turno consumido
    WAITING --> IN_TRANSIT: entra en conexión hacia una restricted
    IN_TRANSIT --> WAITING: turno de tránsito completado, llega a la restricted
    WAITING --> ARRIVED: la zona alcanzada es end_hub
    MOVING --> ARRIVED: llegó directamente a end_hub
    ARRIVED --> [*]: entregado, deja de rastrearse
```

⚠️ **No lo des por sentado — `IN_TRANSIT` no puede interrumpirse**
*(Cap. VII.3)*: *"the drone MUST reach its destination during the next turn. It
can't wait extra turns on the connection."* Un dron en tránsito **no toma
decisiones** el turno siguiente: llega, y punto. Si tu fase de decisión le
pregunta a un dron `IN_TRANSIT` qué quiere hacer, ya has abierto la puerta a que
espere en el aire. Sáltatelo: los drones `IN_TRANSIT` se resuelven automáticamente.

Y como corolario: la zona destino de una `restricted` **tiene que estar
garantizada libre en el turno de llegada** desde el momento en que el dron entra
en la conexión. Eso ya lo garantiza la reserva de
[SP06](./SP06-tabla-reservas.md), que ocupa la zona destino en `T+cost` en el
mismo momento en que reserva la conexión. Si esa reserva falta, un dron puede
quedarse sin sitio donde aterrizar, y no hay recuperación posible.

## Paso 2 — El bucle, con las dos fases

```
función run():
    turno ← 0
    salida ← []

    mientras queden drones sin entregar:

        # (a) replanificar al inicio de cada media ventana,
        #     o antes si a algún dron en tierra se le agotó la ruta
        si turno % (W // 2) == 0 o algún dron en tierra no tiene ruta:
            tabla.clear_from(turno, keep=ids_en_transito)
            rutas ← pathfinder.plan(drones_activos, turno)   # ordena, busca y graba
            para cada dron activo: dron.path ← rutas[dron.id]

        # (b) FASE 1 — DECIDIR (nadie se mueve todavía)
        movimientos ← []
        para cada dron activo:
            si dron.state es IN_TRANSIT:
                movimientos.append(llegada_forzosa(dron))
            si no:
                paso ← dron.siguiente_paso(turno)
                si paso existe y es legal contra el estado del turno:
                    movimientos.append((dron, paso))

        # (c) FASE 2 — APLICAR (todos a la vez)
        para cada (dron, paso) en movimientos:
            aplicar el movimiento, actualizar estado del dron
            si dron.current_zone es end_hub: dron.state ← ARRIVED

        salida.append(formatear(movimientos))
        turno ← turno + 1

        si turno > LIMITE_SEGURIDAD:
            lanzar SimulationError("la simulación no converge")

    devolver salida
```

### Por qué dos fases, en concreto

⚠️ **No lo des por sentado — esto no es una preferencia estética**
La regla del subject es: *"Drones moving out of a zone free up capacity for that
same turn"* *(Cap. VII.3)*. O sea: si el dron A está en `narrow` (capacidad 1) y
se va este turno, el dron B puede entrar en `narrow` **este mismo turno**.

Si aplicas los movimientos según recorres la lista:

- Si procesas B antes que A, ves `narrow` ocupada → B espera. **Mal.**
- Si procesas A antes que B, ves `narrow` libre → B entra. **Bien.**

El resultado depende del orden de la lista, que es un detalle de implementación
arbitrario. Separando decidir de aplicar, **todas** las decisiones se toman
contra el mismo estado (el del turno T, conociendo las salidas previstas), y el
resultado es el mismo con la lista en cualquier orden.

Ese es exactamente el test de cierre que verifica que lo hiciste bien.

### Cómo se cuentan las salidas en la fase 1

Para decidir si B puede entrar en `narrow`, la fase 1 necesita saber que A se va
a ir. Dos formas:

| Forma | Cómo |
|---|---|
| **Confiar en la tabla de reservas** | El pathfinder ya reservó `(narrow, T)` para B y `(narrow, T-1)` para A. La fase 1 solo ejecuta lo planificado |
| **Recalcular la ocupación del turno** | Contar los drones que están en cada zona, restar los que salen, sumar los que entran |

**Recomendación: la primera, con la segunda como verificación.** Si el pathfinder
de SP07 hizo bien su trabajo, la ruta de cada dron **ya es legal** y la fase 1 se
limita a ejecutarla. Recalcular sería duplicar la lógica de capacidades en dos
sitios que pueden divergir.

Pero **verifica** en modo debug: si al aplicar un movimiento detectas una
violación de capacidad, es un bug de SP06 o SP07 y quieres saberlo de inmediato,
no descubrirlo tres mapas después. Un `assert` o un `SimulationError` explícito
aquí vale su peso en oro.

## Paso 3 — La replanificación

```python
if turn % (self.window // 2) == 0:
    self.table.clear_from(turn, keep=in_transit_ids)
    paths = self.pathfinder.plan(active_drones, turn)
    for drone in active_drones:
        drone.path = paths[drone.id]
```

⚠️ **No lo des por sentado — llama a `plan`, no a `find_path` en un bucle**
`plan()` ([SP07](./SP07-whca.md#resuelto-en-plan-la-reserva-provisional))
hace más que ordenar y grabar: antes de planificar a nadie reserva la posición
actual de todos los drones durante la ventana. Si recorres los drones llamando
a `find_path` tú mismo, un dron que planifica antes puede reservar entrar en la
zona de otro que aún no ha planificado y dejarlo sin salida legal. El criterio
de orden se elige al construir el `WhcaPathfinder` (`order=`).

**Por qué `W // 2` y no `W`:** si replanificas justo cuando la ventana se agota,
los drones llegan al límite sin margen de reacción. Replanificando a mitad de
ventana, siempre tienen `W/2` turnos de cooperación por delante. Es el mismo
principio que el *receding horizon control*.

⚠️ **No lo des por sentado — los drones `IN_TRANSIT` no se replanifican**
Un dron en el aire tiene su llegada comprometida: no puedes darle una ruta
nueva a mitad de trayecto porque no puede parar ni dar media vuelta. Exclúyelos
del bucle de replanificación y respeta la reserva que ya tienen, pasando sus ids
en `keep`. Sin `keep`, `clear_from(turno)` borraría la reserva de su zona de
aterrizaje y otro dron podría ocuparla — dejando al primero sin sitio donde
llegar.

Es un bug sutil, devastador, y **muy** difícil de diagnosticar a posteriori.

## Paso 4 — El límite de seguridad

```python
MAX_TURNS_FACTOR = 4

limit = nb_drones * len(graph.zones) * MAX_TURNS_FACTOR
```

⚠️ **Ponlo. No es opcional.** WHCA\* no es completo: existen configuraciones
donde no converge (ver [SP07](./SP07-whca.md), `swap_corridor.txt`). Sin límite,
tu programa **se cuelga** durante la evaluación, y el subject dice que un
programa que se cuelga cuenta como no funcional *(Cap. III.1)*.

Un límite generoso y un `SimulationError` con un mensaje claro es infinitamente
mejor que un cuelgue:

```python
class SimulationError(Exception):
    """La simulación no pudo completarse."""
```

El mensaje debe decir qué pasó y con qué drones: *"No converge tras 340 turnos.
Drones sin entregar: D3 (en narrow), D7 (en corridorA)."* Eso es depurable; "se
colgó" no lo es.

## Paso 5 — Detectar lo imposible antes de empezar

Antes del primer turno, comprueba con `AbstractDistance` que `end_hub` es
alcanzable desde `start_hub`. Si no lo es, el mapa no tiene solución y debes
decirlo en el turno 0, con un mensaje claro — no tras 340 turnos de dar vueltas.

```python
if not self.heuristic.is_reachable(graph.start_hub):
    raise SimulationError(
        "end_hub no es alcanzable desde start_hub en este mapa"
    )
```

Cuesta dos líneas y convierte un cuelgue confuso en un error comprensible.

---

## Tests de cierre (`test/test_simulator.py`)

- [x] `single_drone.txt`: 1 dron, 1 turno, llega
- [x] `linear.txt`: los 2 drones llegan; el número de turnos coincide con el cálculo a mano
- [x] `bottleneck.txt`: los 3 drones llegan sin violar `max_drones=1` en `narrow`
- [x] **Independencia del orden:** ejecuta el mismo mapa con `drones` en orden
      normal y en orden invertido → **mismo número de turnos**. *(El test que
      verifica que las dos fases están bien.)*
- [x] Todos los drones acaban en `ARRIVED`
- [x] Ningún dron `IN_TRANSIT` permanece más de un turno en la conexión
- [x] Mapa sin ruta posible → `SimulationError` en el turno 0, no un cuelgue
- [x] **Validador de invariantes** ([`05-plan-de-pruebas.md`](../05-plan-de-pruebas.md#4-verificación-de-invariantes--el-test-que-más-bugs-caza))
      aplicado a la traza completa de **todos** los mapas

El último es el de mayor retorno de todo el proyecto: un validador independiente
que recorre la traza y comprueba todas las reglas del Cap. VII. Caza regresiones
de SP06, SP07, SP08 y SP09 de una sola vez.

---

## Criterio de salida

- [x] Los 8 tests pasan
- [x] El validador de invariantes pasa en todos los mapas de `maps/valid/`
- [x] El límite de seguridad existe y su mensaje nombra los drones atascados
- [x] `make lint-strict` pasa

## Decisiones a anotar

- Factor del límite de seguridad y por qué ese
- ¿La fase 1 confía en la tabla o recalcula la ocupación?
- ¿Qué pasa si un dron recibe una ruta parcial que se agota antes de la siguiente
  replanificación? *(Debe esperar en el sitio, no quedarse sin estado definido.)*
- Cadencia de replanificación: `W//2` u otra

## Decisiones tomadas

Implementado en `fly_in/simulation/` (`drone.py`, `simulator.py`,
`errors.py`), probado en `test/test_simulator.py` (90 tests). La historia
completa, con trazas reales turno a turno, está en
[`09-narrativa-sp08.md`](../09-narrativa-sp08.md).

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Límite de seguridad `nb_drones × zonas × 4` (`MAX_TURNS_FACTOR`) | Un número fijo | Un dron tarda como mucho 2 turnos por zona (`restricted`); en fila india, `nb_drones` veces eso. El 4 deja el doble de margen. Challenger: 25 × 54 × 4 = 5400 frente a 43 reales |
| La fase 1 **confía en la tabla** (ejecuta las rutas planificadas) y la fase 2 **verifica** recontando zonas y conexiones sin mirar la tabla (`_verify`) | Recalcular la ocupación para decidir | Una sola fuente de verdad para las capacidades (SP06/SP07); la verificación independiente convierte un bug de SP06/SP07 en un `SimulationError` en el turno exacto |
| Ruta agotada antes de la siguiente replanificación → **se replanifica en ese turno** | Esperar en el sitio | Esperar sin reserva deja la zona libre en la tabla y otro dron podría planificar entrar. Replanificando, la espera, si hace falta, queda reservada. En la práctica casi no ocurre: las rutas parciales cubren `W` turnos y se replanifica cada `W/2` |
| Cadencia `max(1, W // 2)` | `W` | Siempre quedan `W/2` turnos de cooperación por delante; el `max` evita dividir por cero con `W = 1` |
| En tránsito: `current_zone` sigue siendo la zona de origen y `transit_connection` dice dónde está | Poner `current_zone = None` | El dron no ocupa ninguna zona en el aire (la verificación lo excluye), y la salida necesita el origen para el segundo turno. `Optional[Zone]` obligaría a comprobar `None` en todas partes |
| La traza es `List[List[Move]]`, un `Move` por dron que se mueve; `arrives=False` marca el primer turno de un tránsito | Devolver texto ya formateado | Separar simulación y formato (SP09). `Move` lleva justo lo que SP09 necesita: `D<id>-<zona>` si `arrives`, `D<id>-<conexión>` si no |
| Los drones los crea el `Simulator` y son públicos (`sim.drones`) | Recibirlos por parámetro | El test de independencia del orden invierte la lista antes de `run()` |
| Orden de planificación por id (el de `WhcaPathfinder` por defecto) | `farthest_first`, `rotating` | Medido en los 10 mapas oficiales: `by_id` y `nearest_first` empatan en todos; `farthest_first` casi triplica los turnos (challenger 124 frente a 43) por el coste de la reserva provisional de SP07; `rotating` también empeora (74). Tabla completa con W = 4, 8 y 16 en [SP11](./SP11-benchmarks-y-readme.md) |
| `W = 8` por defecto | 4 o 12 | Con `W` 4, 8 y 12 los turnos son idénticos en los 19 mapas; 8 queda como valor de partida y el ajuste fino es de SP11 |

**Resultados actuales (W = 8, orden por id)**, fijados en
`test_official_benchmarks`:

| Mapa | Drones | Objetivo del subject | Turnos | Referencia de Mario |
|---|---|---|---|---|
| easy/01 linear path | 2 | ≤ 6 | 4 | 4 |
| easy/02 simple fork | 4 | ≤ 8 | 4 | 4 |
| easy/03 basic capacity | 4 | ≤ 6 | 4 | 4 |
| medium/01 dead end trap | 5 | ≤ 12 | 8 | 8 |
| medium/02 circular loop | 6 | ≤ 15 | **15** | 10 |
| medium/03 priority puzzle | 5 | ≤ 12 | 7 | 6 |
| hard/01 maze nightmare | 8 | ≤ 30 | 13 | 13 |
| hard/02 capacity hell | 12 | ≤ 35 | 16 | 16 |
| hard/03 ultimate challenge | 15 | ≤ 45 | 26 | 26 |
| challenger | 25 | batir 45 | 43 | 43 |

medium/02 sale peor que la referencia por la lectura estricta de `restricted`
(conexión ocupada los dos turnos del tránsito, decisión de SP06): el enlace
`loop_b-exit_point` tiene capacidad 1, así que solo entra un dron cada 2
turnos, y 6 drones necesitan exactamente 15. Es el óptimo con esa lectura, no
un fallo de la búsqueda. Ver la narrativa, sección 6.3. medium/03 (7 frente
a 6) tiene la misma causa: la segunda ruta por `slow_path1` (`restricted`)
solo admite un dron cada 2 turnos. Ejecutando este mismo algoritmo con la
lectura permisiva salen exactamente 10 y 6 (ver
[`12-narrativa-sp11.md`](../12-narrativa-sp11.md)).
