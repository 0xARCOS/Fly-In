# SP09 — `OutputFormatter`: la salida del subject ✅

**Objetivo:** volcar la simulación en el formato textual **exacto** del Cap.
VII.5. Es la parte que un evaluador compara literalmente, carácter a carácter.

**Prerequisitos:** [SP08](./SP08-drone-y-simulador.md) verde.

**Criterio de salida:** la salida de tus mapas coincide con el formato del
subject, y `stdout` no contiene absolutamente nada más.

---

## Paso 1 — Las cinco reglas del formato

*(Cap. VII.5, literal)*

1. Una **línea por turno**.
2. En cada línea, todos los movimientos del turno **separados por espacios**.
3. Cada movimiento: `D<ID>-<zona>`, o `D<ID>-<conexión>` si el dron va en vuelo
   hacia una `restricted`.
4. Los drones que **no se mueven** se **omiten** de esa línea.
5. Los drones que llegan a `end_hub` quedan entregados y no aparecen más.

Ejemplo del subject:

```
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

## Paso 2 — La clase

`fly_in/output/formatter.py` (crea la carpeta y su `__init__.py`)

```python
class OutputFormatter:
    """Formatea los movimientos de un turno según el Cap. VII.5 del subject."""

    def format_move(self, drone: Drone, step: Step) -> str:
        """Un movimiento: 'D1-roof1' o, en tránsito, 'D1-hub-roof1'."""

    def format_turn(self, moves: list[tuple[Drone, Step]]) -> str:
        """Una línea de turno. Cadena vacía si no hubo movimientos."""
```

```python
def format_move(self, drone: Drone, step: Step) -> str:
    if drone.state is DroneState.IN_TRANSIT:
        target = step.connection.name      # 'hub-roof1'
    else:
        target = step.zone.name            # 'roof1'
    return f"D{drone.id}-{target}"
```

⚠️ **No lo des por sentado — el tránsito produce DOS líneas, no una**
Un movimiento a una `restricted` cuesta 2 turnos y por tanto aparece en dos
turnos consecutivos de la salida:

```
D1-hub-roof1     # turno T: entró en la conexión
D1-roof1         # turno T+1: llegó a la zona
```

No es un movimiento que se imprima una vez con coste 2. Si tu formateador
imprime solo la llegada, la salida tendrá menos líneas que turnos de simulación
y no cuadrará con el recuento.

⚠️ **No lo des por sentado — el nombre de la conexión es fijo, no direccional**
`Connection.name` es `"<zone_a>-<zone_b>"` en el orden en que apareció en el
archivo de mapa. Un dron que recorra la conexión en sentido contrario imprime
**el mismo nombre**, porque es la misma conexión. No intentes darle la vuelta
según la dirección del dron: el subject dice *"`<connection>` is the name of the
connection"*, no "el nombre orientado según el trayecto".

## Paso 3 — Los tres puntos que el subject deja abiertos

Decide, documenta en el `README.md` y sé consistente:

| Punto | Decisión de este proyecto | Por qué |
|---|---|---|
| Turno sin ningún movimiento | **No se imprime línea** | Una línea vacía no aporta información y complica el recuento visual de turnos |
| Orden de los movimientos en la línea | **Por ID de dron ascendente** | Determinista, reproducible entre ejecuciones, y comparable en un test |
| Qué se imprime al terminar | **Nada en `stdout`**; métricas y resumen en `stderr` | Ver abajo |

⚠️ **No lo des por sentado — `stdout` solo lleva las líneas de turno**
Esta es la decisión más importante del subproyecto. Si mezclas en `stdout` los
colores ANSI de [SP10](./SP10-visualizacion.md), las métricas o cualquier
mensaje, un evaluador no puede hacer:

```console
$ make run MAP=maps/easy/01.txt > salida.txt
$ wc -l salida.txt        # = número de turnos, directo
```

Todo lo que no sea una línea de turno va a `stderr`. Es una línea de código
(`file=sys.stderr`) y es lo que hace tu salida verificable automáticamente.

## Paso 4 — Cuenta los turnos con la salida, no aparte

El número de turnos es **tu nota** *(Cap. VII.6)*. Calcúlalo como el número de
líneas que emitiste, no con un contador separado del formateador: si el contador
y las líneas divergen (porque un turno sin movimientos no imprimió), estarás
informando de un número distinto del que el evaluador puede contar.

🔍 **Verifica** en cada mapa: `número de líneas de stdout == turnos reportados`.
Si no coinciden, tienes un turno fantasma o una línea de más, y en ambos casos
tu métrica está mal.

---

## Tests de cierre (`test/test_output_format.py`)

- [x] Un movimiento simple da exactamente `D1-roof1`
- [x] Un tránsito da `D1-hub-roof1`, y el turno siguiente `D1-roof1`
- [x] Dos drones en el mismo turno: `D1-a D2-b`, separados por **un** espacio
- [x] Un dron que no se mueve **no aparece** en la línea
- [x] Un dron entregado **no aparece** en ninguna línea posterior
- [x] Los movimientos salen ordenados por ID
- [x] Un turno sin movimientos no produce línea
- [x] `linear.txt` completo: la salida coincide con la esperada escrita a mano
- [x] Ninguna línea de `stdout` contiene códigos ANSI ni texto que no sea `D<n>-<nombre>`

El último se comprueba con una expresión regular sobre toda la salida:
`^D\d+-[^\s]+( D\d+-[^\s]+)*$` por línea. Es la red que garantiza que nada se
cuela en `stdout`.

---

## Criterio de salida

- [x] Los 9 tests pasan
- [x] `make run MAP=maps/valid/linear.txt` produce una salida que puedes
      verificar a mano contra el mapa
- [x] `stdout` solo contiene líneas de turno
- [x] `make lint-strict` pasa

## Decisiones a anotar

- Los tres puntos abiertos del paso 3, con su justificación
- La salida real de `linear.txt` y `bottleneck.txt` — **guárdala**, va literal en
  la sección *"Example input and expected output"* del `README.md`, que el
  subject exige *(Cap. VIII)*

## Decisiones tomadas

Implementado en `fly_in/output/formatter.py`, probado en
`test/test_output_format.py` (46 tests). La historia completa está en
[`SP09-narrativa.md`](../narrativas/SP09-narrativa.md).

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| `format_move(move)` recibe un `Move` de SP08, no `(Drone, Step)` | La firma del paso 2 | El `Move` ya dice si el dron acaba el turno en la conexión (`arrives=False`) o en la zona. Con `(Drone, Step)` habría que mirar `drone.state`, que es el estado *después* de aplicar el turno y obliga a razonar sobre cuándo se consulta |
| Turno sin movimientos → sin línea | Línea vacía | Un turno así deja el mundo idéntico (nadie puede estar en el aire, porque quien lo está aterriza obligatoriamente), así que omitirlo no cambia la legalidad de lo que sigue. Además, el simulador actual no produce ninguno en los 19 mapas |
| Orden por id ascendente | Orden de la lista | Determinista y comparable en un test; `_apply` ya los devuelve así, y el formateador vuelve a ordenarlos para no depender de ello |
| `stdout` solo con líneas de turno; todo lo demás, a `stderr` | Resumen al final de `stdout` | `make run > salida.txt` y `wc -l` da el número de turnos. El `Makefile` lleva `@` en `run` para que `make` no cuele el comando en `stdout` |
| El número de turnos se cuenta con las líneas (`Metrics.turns` cuenta turnos con movimientos) | Un contador aparte | La cifra que reportamos es la que el evaluador puede contar |

Salidas reales, para el `README.md`:

`linear.txt`
```
D1-waypoint1
D1-waypoint2 D2-waypoint1
D1-goal D2-waypoint2
D2-goal
```

`bottleneck.txt`
```
D1-narrow
D1-goal D2-narrow
D2-goal D3-narrow
D3-goal
```
