# SP04 — Dijkstra: la ruta de un solo dron ⬜

**Objetivo:** dado el grafo, calcular la ruta de coste mínimo `start_hub →
end_hub` **ignorando por completo a los demás drones**.

**Prerequisitos:** [SP02](./SP02-parser.md) verde.

**Criterio de salida:** para cualquier mapa, la ruta calculada es óptima y
verificable a mano; nunca pasa por `blocked`; prefiere `priority` en los
empates.

**Por qué este subproyecto es el más importante del proyecto:** todo lo que
viene después lo reutiliza. [SP05](./SP05-heuristica-abstracta.md) es este mismo
algoritmo ejecutado hacia atrás. [SP07](./SP07-whca.md) es este algoritmo con
una dimensión más. Si Dijkstra tiene un bug sutil, lo vas a pagar tres veces.

---

## Paso 0 — Crear el paquete

```console
$ mkdir -p fly_in/pathfinding && touch fly_in/pathfinding/__init__.py
```

Sin el `__init__.py` la carpeta no es importable. Créalo ahora.

## Paso 1 — Primero, completar `Zone`

Dijkstra necesita dos preguntas que `Zone` todavía no sabe responder. Añádelas
en `fly_in/models/zone.py`:

```python
MOVEMENT_COSTS = {"normal": 1, "priority": 1, "restricted": 2}


class Zone:
    def movement_cost(self) -> int:
        """Turnos que cuesta ENTRAR en esta zona.

        Raises:
            ValueError: si la zona es 'blocked' (no se puede entrar en ella).
        """

    def is_traversable(self) -> bool:
        """False solo para las zonas 'blocked'."""
```

⚠️ **No lo des por sentado — el coste es de la zona DESTINO, siempre**
*(Cap. VII.3)*: el coste de un movimiento lo fija el tipo de la zona a la que
llegas, **nunca** el de la que dejas ni el de la conexión. Moverse de una
`restricted` a una `normal` cuesta 1, no 2. Este es el malentendido número uno
del proyecto y produce rutas que parecen correctas pero cuestan de más.

⚠️ **No lo des por sentado — `movement_cost()` de una `blocked` debe fallar**
Es tentador devolver `float("inf")` o un número gigante. Lanzar una excepción es
mejor: si llegas a preguntar el coste de una `blocked`, es que tu filtro de
`is_traversable()` tiene un agujero, y quieres enterarte ahora y no tres capas
más arriba con una ruta rarísima.

## Paso 2 — Qué devuelve la búsqueda

Antes de escribir el algoritmo, decide el tipo de retorno. La firma:

```python
class Dijkstra:
    """Camino de coste mínimo para un dron, sin considerar a los demás."""

    def __init__(self, graph: Graph) -> None: ...

    def find_path(self, origin: Zone, target: Zone) -> Optional[list[Zone]]:
        """Ruta de coste mínimo de `origin` a `target`.

        Returns:
            La lista de zonas desde origin (incluido) hasta target (incluido),
            o None si no existe ninguna ruta.
        """

    def cost_of(self, path: list[Zone]) -> int:
        """Coste total en turnos de recorrer `path`."""
```

⚠️ **No lo des por sentado — "no hay ruta" no es un error**
Un grafo donde `end_hub` es inalcanzable (rodeado de `blocked`, o simplemente
desconectado) es un grafo **válido**. El parser lo acepta y debe aceptarlo. Que
no haya camino es un resultado legítimo de la búsqueda, y por eso se devuelve
`None` en vez de lanzar. Quien decide qué hacer con eso es el simulador
([SP08](./SP08-drone-y-simulador.md)), que sí debe reportarlo como error de
simulación.

## Paso 3 — El algoritmo

```
función find_path(origin, target):
    dist ← {}                          # zona -> mejor coste conocido
    prev ← {}                          # zona -> zona anterior en la mejor ruta
    heap ← [(0, 0, contador++, origin)]
    visitadas ← conjunto vacío

    mientras heap no esté vacío:
        (coste, neg_prio, _, zona) ← heappop(heap)

        si zona en visitadas: continuar       # entrada obsoleta, descártala
        añadir zona a visitadas

        si zona es target: devolver reconstruir(prev, target)

        para cada conexión en graph.neighbors(zona):
            vecino ← conexión.other_end(zona)
            si no vecino.is_traversable(): continuar
            nuevo_coste ← coste + vecino.movement_cost()
            nueva_prio ← neg_prio - (1 si vecino es priority si no 0)

            si (nuevo_coste, nueva_prio) mejora lo conocido de vecino:
                dist[vecino] ← (nuevo_coste, nueva_prio)
                prev[vecino] ← zona
                heappush(heap, (nuevo_coste, nueva_prio, contador++, vecino))

    devolver None
```

### Las tres claves del heap

El elemento del heap es una **tupla de 4**, y cada posición tiene su razón:

| Pos | Valor | Por qué |
|---|---|---|
| 0 | `coste` | El criterio principal: minimizar turnos |
| 1 | `-num_priority` | Desempate: negado para que **más** zonas `priority` sea **menor** y por tanto gane |
| 2 | `contador` | Desempate final estable, **imprescindible** |
| 3 | `zona` | El dato |

⚠️ **No lo des por sentado — sin el contador obtienes un `TypeError`**
`heapq` compara tuplas elemento a elemento. Si dos entradas empatan en coste y
en prioridad, Python pasa al tercer elemento. Si ahí estuviera el `Zone`,
intentaría hacer `Zone < Zone` y reventaría con
`TypeError: '<' not supported between instances of 'Zone'`. Un entero
incremental global lo hace imposible: dos entradas nunca empatan en el
contador. Y como es incremental, empata a favor del que se descubrió antes, que
es un comportamiento determinista y reproducible.

⚠️ **No lo des por sentado — `heapq` no sabe actualizar prioridades**
El Dijkstra de los libros "disminuye la clave" de un nodo ya en la cola.
`heapq` no ofrece esa operación. La técnica estándar en Python es **lazy
deletion**: haces `heappush` de la entrada nueva sin borrar la vieja, y al hacer
`heappop` descartas las entradas de zonas que ya visitaste. Por eso el bucle
empieza con `si zona en visitadas: continuar`. El heap tendrá entradas obsoletas;
no importa, solo cuesta algo de memoria.

⚠️ **No lo des por sentado — marca visitada al SACAR, no al meter**
Si marcas la zona como visitada en el `heappush`, la estás cerrando antes de
saber si ese era el camino más barato hacia ella. El invariante de Dijkstra es
que cuando una zona **sale** del heap, su distancia es definitiva — porque
cualquier otro camino pasaría por un nodo de coste mayor o igual. Marcar al
meter rompe ese invariante y produce rutas subóptimas en grafos con costes
distintos (o sea, en cuanto haya una `restricted`).

### La reconstrucción de la ruta

`prev` guarda, para cada zona, de dónde llegaste a ella. Para reconstruir vas
desde `target` hacia atrás hasta `origin`, y **das la vuelta a la lista**:

```python
path = []
node = target
while node is not None:
    path.append(node)
    node = prev.get(node)
path.reverse()
```

🔍 **Verifica** — la primera zona de la lista debe ser `origin` y la última
`target`. Si te sale al revés, te falta el `reverse()`; es un despiste tan
común que merece una comprobación con `assert` en el propio test.

---

## Paso 4 — El desempate `priority`, con cuidado

⚠️ **No lo des por sentado — `priority` NO es más barata**
Cuesta 1, igual que `normal` *(Cap. VI)*. Si la implementas como coste 0.5 o 0,
el coste total de la ruta deja de coincidir con el número de turnos que tarda el
dron — y toda la simulación, que cuenta turnos, dejará de cuadrar con el
pathfinding, que cuenta costes inventados. Además la heurística de SP05 dejaría
de ser admisible.

El segundo elemento de la tupla del heap es la forma correcta: el coste manda,
y solo cuando dos rutas empatan en coste, gana la que ha acumulado más zonas
`priority`.

🔍 **Verifica** con un mapa en diamante: `start` se bifurca en dos rutas de dos
zonas cada una hasta `goal`; una rama es `normal`+`normal`, la otra
`priority`+`priority`. Ambas cuestan 2. El algoritmo debe elegir la segunda,
siempre, independientemente del orden en que estén escritas las conexiones en el
archivo. Ese "independientemente del orden" es lo que el test debe comprobar:
escribe el mapa en los dos órdenes y verifica que gana la misma rama.

---

## Tests de cierre (`test/test_dijkstra.py`)

- [ ] `linear.txt`: la ruta es exactamente `[start, waypoint1, waypoint2, goal]`, coste 3
- [ ] `single_drone.txt`: ruta `[start, goal]`, coste 1
- [ ] `restricted_chain.txt`: cada `restricted` suma 2 al coste total
- [ ] `blocked_detour.txt`: la ruta rodea la zona `blocked`, que no aparece en el resultado
- [ ] `priority_tie.txt`: gana la rama `priority`, en los dos órdenes de escritura del mapa
- [ ] Grafo con `end_hub` desconectado: devuelve `None`, no lanza
- [ ] `origin is target`: devuelve `[origin]`, coste 0
- [ ] La ruta devuelta es **consistente**: cada par consecutivo está realmente conectado en el grafo

El último test es el más valioso y el que menos gente escribe: recorre la ruta
resultante y comprueba contra `graph.neighbors()` que cada salto existe de
verdad. Caza de un plumazo cualquier error en la reconstrucción.

---

## Criterio de salida

- [ ] Los 8 tests pasan
- [ ] Puedes calcular a mano el coste de una ruta en `bottleneck.txt` y coincide
- [ ] `make lint-strict` pasa

## Decisiones a anotar

- ¿`Optional[list[Zone]]` o una excepción `NoPathError`? *(La guía recomienda
  `None`: no hay ruta es un resultado, no un fallo.)*
- ¿`Dijkstra` como clase con el grafo en el constructor, o función suelta?
  *(Clase: el subject exige diseño orientado a objetos, y en SP05 vas a querer
  reutilizar la instancia.)*
- ¿El desempate `priority` cuenta zonas acumuladas en la ruta, o solo mira la
  zona destino? *(Acumuladas es lo correcto: queremos la ruta con más
  `priority` en total, no la que da el último paso a una.)*
