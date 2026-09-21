# SP07 — `WhcaPathfinder`: la búsqueda cooperativa ⬜

**Objetivo:** buscar rutas en **espacio-tiempo**, esquivando las reservas de los
drones que ya planificaron, dentro de una ventana de `W` turnos.

**Prerequisitos:** [SP05](./SP05-heuristica-abstracta.md) y
[SP06](./SP06-tabla-reservas.md) **verdes**. Sin excepción: este es el
subproyecto donde los bugs de los anteriores se manifiestan disfrazados.

**Criterio de salida:** un dron solo replica la ruta de Dijkstra; dos drones
ante un cuello de botella se alternan sin bloquearse; un dron sin ruta libre
devuelve ruta parcial, no `None`.

---

## Paso 1 — El cambio mental

Hasta ahora el estado de búsqueda era `zona`. Ahora es **`(zona, turno)`**.

Esa única diferencia convierte "el dron 2 estará en `corridorA` en el turno 5" en
un obstáculo del espacio de búsqueda, exactamente igual que una zona `blocked` —
pero solo en el turno 5. La búsqueda lo esquiva **sola**. No escribes ninguna
detección de colisiones: la colisión simplemente no está entre los estados
alcanzables.

## Paso 2 — El nodo de búsqueda

```python
@dataclass(frozen=True, order=True)
class SearchNode:
    f: int              # g + h — PRIMERO, para que el heap ordene por él
    g: int              # turnos gastados desde el inicio de la ventana
    turn: int           # turno absoluto de simulación
    zone_name: str
    tie: int            # contador incremental, desempate estable
```

⚠️ **No lo des por sentado — el orden de los campos ES el orden del heap**
`@dataclass(order=True)` genera los comparadores comparando los campos **en el
orden en que están declarados**, como si fueran una tupla. Si pones `g` antes
que `f`, tu A\* se convierte silenciosamente en un Dijkstra: seguirá dando rutas
correctas pero explorará muchísimo más. El primer campo debe ser `f`.

⚠️ **No lo des por sentado — `tie` no es opcional (otra vez)**
Mismo problema que en [SP04](./SP04-dijkstra.md): si dos nodos empatan en todos
los campos anteriores, Python compara el siguiente. Con `zone_name` (un `str`)
no reventaría, pero desempataría por orden alfabético del nombre de la zona —
que es arbitrario y no reproducible entre mapas. Un contador incremental global
desempata a favor del nodo descubierto antes: determinista y sensato.

⚠️ **No lo des por sentado — `zone_name`, no `Zone`**
`frozen=True` hace la dataclass hasheable, pero solo si **todos** sus campos lo
son. `Zone` no define `__hash__` explícito (hashea por identidad, que funciona
pero es frágil) y además no es comparable con `<`, lo que rompería `order=True`.
Guarda el nombre y resuelve el objeto con `graph.get_zone()` cuando lo
necesites.

## Paso 3 — La búsqueda

```
función find_path(dron, turno_inicial, W):
    inicio ← posición actual del dron
    abiertos ← heap con SearchNode(f=h(inicio), g=0, turn=turno_inicial, zone=inicio)
    cerrados ← conjunto vacío de (zona, turno)
    mejor ← None                  # nodo más prometedor alcanzado en la ventana

    mientras abiertos no esté vacío:
        n ← heappop(abiertos)

        si n.zone es end_hub:
            devolver reconstruir_ruta(n)          # éxito completo

        si n.turn - turno_inicial >= W:
            si mejor es None o n.f < mejor.f: mejor ← n
            continuar                              # fin de ventana, no expandir

        si (n.zone, n.turn) en cerrados: continuar
        añadir (n.zone, n.turn) a cerrados

        # --- vecinos por conexión ---
        para cada conexión en graph.neighbors(n.zone):
            vecino ← conexión.other_end(n.zone)
            si no vecino.is_traversable(): saltar
            si no heuristica.is_reachable(vecino): saltar
            coste ← vecino.movement_cost()                    # 1 o 2
            si no tabla.link_has_room(conexión, n.turn): saltar
            si tabla.would_swap(n.zone, vecino, n.turn): saltar
            si no tabla.zone_has_room(vecino, n.turn + coste): saltar
            push SearchNode(f = n.g + coste + h(vecino),
                            g = n.g + coste,
                            turn = n.turn + coste,
                            zone = vecino)

        # --- esperar en el sitio, que es un vecino más ---
        si tabla.zone_has_room(n.zone, n.turn + 1):
            push SearchNode(f = n.g + 1 + h(n.zone),
                            g = n.g + 1,
                            turn = n.turn + 1,
                            zone = n.zone)

    devolver reconstruir_ruta(mejor)     # ruta parcial hasta el borde de la ventana
```

---

## Los cuatro sitios donde esto se rompe

### 1. Olvidar "esperar" como vecino

⚠️ Sin el bloque final, un dron ante un pasillo temporalmente ocupado **no
encuentra ninguna ruta**, y tu algoritmo concluirá que el mapa es irresoluble.
Esperar es el mecanismo por el que un dron cede el paso, y el subject lo lista
como movimiento válido explícito *(Cap. VII.3: "Stay in place")*.

Es el bug número uno de este subproyecto y el síntoma es engañoso: todo funciona
con un dron y falla con dos.

### 2. Cerrar por `zona` en vez de por `(zona, turno)`

⚠️ La misma zona en el turno 3 y en el turno 9 son **estados distintos**. Si
cierras solo por zona, eliminas la posibilidad de volver a pasar por ahí más
tarde — que es exactamente lo que a veces hace falta (apartarse y volver). Y
además rompes el "esperar": esperar significa generar `(misma zona, turno+1)`,
que con cerrado-por-zona estaría ya cerrado y se descartaría de inmediato.

### 3. Devolver `None` cuando se agota la ventana

⚠️ Que la ventana se agote **no es un fallo**: es el comportamiento normal de
WHCA\*. La ruta parcial hasta el nodo más prometedor **es** el resultado, y el
simulador la ejecutará hasta la siguiente replanificación.

Solo hay fracaso real si el heap se vacía sin haber alcanzado **ningún** nodo —
lo que significa que el dron está completamente encerrado ahora mismo. Incluso
entonces, la respuesta razonable no es `None` sino "quédate donde estás este
turno": una ruta de un solo elemento.

### 4. Aplicar la ventana antes de comprobar el objetivo

⚠️ Mira el orden en el pseudocódigo: primero se comprueba si `n` es `end_hub`,
**después** si se agotó la ventana. Al revés, un dron que llega al objetivo
justo en el turno `W` sería descartado como "fuera de ventana" y daría una
vuelta extra sin ningún motivo.

---

## Paso 4 — La clase

`fly_in/pathfinding/whca.py`

```python
class WhcaPathfinder:
    """Windowed Hierarchical Cooperative A* (Silver, 2005).

    Busca en espacio-tiempo (zona, turno) respetando las reservas de los
    drones que ya planificaron, dentro de una ventana de `window` turnos.
    Más allá de la ventana confía en la heurística abstracta.
    """

    def __init__(self, graph: Graph, heuristic: AbstractDistance,
                 table: ReservationTable, window: int = 8) -> None: ...

    def find_path(self, drone: Drone, start_turn: int) -> list[Step]:
        """Ruta del dron desde su posición actual, dentro de la ventana.

        Returns:
            Lista de pasos, posiblemente parcial (hasta el borde de la
            ventana). Nunca vacía: en el peor caso, esperar en el sitio.
        """
```

### El tipo `Step`

Un paso no es solo una zona: el simulador necesita saber **en qué turno** llega
y **por qué conexión** pasa (para nombrarla en la salida si es un tránsito).

```python
@dataclass(frozen=True)
class Step:
    zone: Zone                        # dónde acaba este paso
    arrival_turn: int                 # turno absoluto de llegada
    connection: Optional[Connection]  # None si es una espera en el sitio
    cost: int                         # 1, o 2 si el destino es restricted
```

Devolver `list[Zone]` a secas te obligaría a re-deducir la conexión y los turnos
en el simulador, y esa deducción tiene casos raros con las esperas. Devuelve la
información que ya tienes.

## Paso 5 — Grabar la ruta en la tabla

En cuanto un dron termina de planificar, su ruta se **graba** antes de que
planifique el siguiente. Si no lo haces, todos los drones planifican contra la
misma tabla vacía y obtienes N copias de la misma ruta: todos chocando.

```python
for step in path:
    if step.connection is None:
        table.reserve_wait(step.zone, step.arrival_turn)
    else:
        table.reserve_move(prev_zone, step.zone, step.connection,
                           step.arrival_turn - step.cost, step.cost)
```

---

## Paso 6 — El orden de planificación

Quien planifica primero se lleva las mejores reservas. Tres criterios, discutidos
en [`04-algoritmo.md`](../04-algoritmo.md#4-la-prioridad-entre-drones):

- **Por ID** — determinista y trivial, pero el dron 1 acapara siempre.
- **Por `h(posición)` descendente** — los más lejanos eligen primero. Suele
  reducir el turno del último en llegar, que es tu métrica.
- **Rotatorio** — reparte la ventaja entre ventanas.

Impleméntalo como un parámetro intercambiable (una función o una estrategia), no
como un `sorted()` incrustado. Vas a querer comparar dos criterios en
[SP11](./SP11-benchmarks-y-readme.md) sin editar la búsqueda.

---

## Tests de cierre (`test/test_whca.py`)

Escríbelos **en este orden**. Cada uno solo tiene sentido si el anterior pasa.

- [ ] **Un dron, tabla vacía:** la ruta es idéntica a la de `Dijkstra` de SP04.
      *(Si esto falla, el bug está en la búsqueda, no en la cooperación.)*
- [ ] **Un dron, mapa con `blocked`:** la rodea
- [ ] **Dos drones, `bottleneck.txt`:** el segundo espera un turno y pasa; ninguno se queda bloqueado
- [ ] **Dos drones, `bottleneck.txt`:** las rutas no violan `max_drones=1` en `narrow` en ningún turno
- [ ] **Tres drones, `bottleneck.txt`:** los tres llegan; se alternan
- [ ] **Ventana pequeña (`W=2`) en un mapa largo:** devuelve ruta **parcial**, nunca `None`
- [ ] **Dron encerrado** (todos los vecinos reservados): devuelve la espera en el sitio, no `None`
- [ ] **Ruta por `restricted`:** el tránsito reserva la conexión dos turnos consecutivos
- [ ] **`swap_corridor.txt`:** dos drones en sentidos opuestos por un pasillo de una zona. **Documenta qué pasa**, sea lo que sea: es el caso patológico conocido de WHCA\*

El último test no tiene un resultado "correcto" prefijado. Su valor es que
**conozcas y documentes** el comportamiento de tu algoritmo en el caso donde la
teoría dice que puede fallar. En la review, "aquí mi algoritmo no converge y sé
por qué" vale muchísimo más que fingir que siempre funciona.

---

## Criterio de salida

- [ ] Los 9 tests pasan (o el noveno está documentado como limitación conocida)
- [ ] `W` es un parámetro, no una constante incrustada
- [ ] El criterio de prioridad es intercambiable
- [ ] `make lint-strict` pasa

## Decisiones a anotar

- Valor de `W` por defecto y por qué
- Criterio de prioridad elegido, con la comparación que lo respalda
- ¿Implementaste la regla anti-cruce (`would_swap`)? *(Ver [SP06](./SP06-tabla-reservas.md).)*
- Comportamiento en `swap_corridor.txt` — **la limitación que vas a documentar en el README**
