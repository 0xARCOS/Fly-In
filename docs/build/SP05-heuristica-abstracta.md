# SP05 — `AbstractDistance`: la heurística ⬜

**Objetivo:** responder en tiempo constante a *"¿cuál es el coste mínimo real
desde la zona X hasta `end_hub`, si no hubiera ningún otro dron?"*

**Prerequisitos:** [SP04](./SP04-dijkstra.md) verde.

**Criterio de salida:** `h(end_hub) == 0`, y `h(zona)` coincide con el coste que
da Dijkstra desde esa zona en varios mapas de prueba.

> ⚠️ **Este es el subproyecto que no puedes dejar a medias.** Todo lo que viene
> después se apoya en que esta tabla sea correcta, y un error aquí produce rutas
> subóptimas que **parecerán bugs del cooperativo**. Vas a depurar SP07 durante
> horas buscando un fallo que está aquí. No sigas sin los tests verdes.

---

## Paso 1 — Entender por qué esto existe

A\* necesita una heurística `h(n)`: una estimación de lo que queda desde `n`
hasta el objetivo. La calidad de `h` decide cuántos nodos explora la búsqueda.

Tienes dos candidatas:

| Heurística | Coste de calcularla | Calidad |
|---|---|---|
| Distancia euclídea entre coordenadas `x`/`y` | Gratis | **Mala.** Ignora la topología |
| Distancia real por el grafo hasta `end_hub` | Un Dijkstra al arrancar | **Perfecta** para este problema |

⚠️ **No lo des por sentado — por qué la euclídea es mala aquí**
Las coordenadas de este mapa **no definen adyacencia** (ver
[`00-el-problema.md`](../00-el-problema.md#3-el-grafo)). Una zona puede estar
geométricamente pegada al objetivo y a la vez a quince saltos de distancia por
el grafo, o al otro lado de un muro de `blocked`. La euclídea mandará al dron
directo a un callejón sin salida porque "parece" que se acerca, y A\* expandirá
montañas de nodos inútiles antes de darse cuenta.

La distancia real por el grafo no tiene ese problema: **ya sabe** que el
callejón no lleva a ninguna parte, porque lo ha recorrido.

## Paso 2 — Por qué se calcula HACIA ATRÁS

Quieres `h(X)` para **todas** las zonas X. Dos formas:

- Un Dijkstra desde cada zona hasta `end_hub`: `V` ejecuciones. Caro y absurdo.
- **Un** Dijkstra desde `end_hub` recorriendo el grafo al revés: te da de golpe
  la distancia de *todas* las zonas al objetivo. Una ejecución.

Y aquí viene la buena noticia: como tus conexiones son **bidireccionales**,
"recorrer al revés" no requiere construir ningún grafo inverso. Recorres el
grafo exactamente igual, partiendo de `end_hub`. Las aristas son las mismas.

## Paso 3 — El detalle delicado: el coste al ir hacia atrás

**Esta es la única parte difícil del subproyecto.** Léela dos veces.

En el recorrido normal, el coste de ir de `A` a `B` es `B.movement_cost()` — el
coste de **entrar en el destino**.

Al recorrer hacia atrás partiendo de `end_hub`, estás expandiendo de `B` hacia
`A`. Pero el movimiento que esa arista representa en la realidad **sigue siendo
`A → B`**: el dron irá de `A` a `B`, y pagará el coste de entrar en `B`.

Entonces, ¿qué sumas?

Piénsalo en términos de lo que significa `h`. `h(A)` es *el coste de ir desde A
hasta el objetivo*. Si `A` conecta con `B`, ese coste es:

```
h(A) = coste_de_entrar_en_B  +  h(B)
```

Porque el dron, desde `A`, primero paga por entrar en `B` y luego le queda
`h(B)`. Así que al expandir de `B` hacia `A`, **sumas el coste de `B`**, no el
de `A`.

⚠️ **No lo des por sentado — el error clásico es sumar el coste de `A`**
Por analogía con el Dijkstra normal ("sumo el coste del nodo al que llego"), es
casi automático escribir `nuevo = dist[B] + A.movement_cost()`. Es incorrecto. La
fórmula es `nuevo = dist[B] + B.movement_cost()`.

Observa la consecuencia interesante: el coste de la **propia** zona `A` nunca
entra en `h(A)`. Correcto: ese coste lo pagó el dron al entrar en `A`, y ya está
pagado cuando preguntas cuánto le queda.

🔍 **Verifica a mano.** Mapa lineal `start → a → b → goal`, todo `normal`:

| | Cálculo | Resultado |
|---|---|---|
| `h(goal)` | punto de partida | **0** |
| `h(b)` | `h(goal) + goal.cost` = 0 + 1 | **1** |
| `h(a)` | `h(b) + b.cost` = 1 + 1 | **2** |
| `h(start)` | `h(a) + a.cost` = 2 + 1 | **3** |

Y ahora marca `b` como `restricted` (coste 2):

| | Cálculo | Resultado |
|---|---|---|
| `h(goal)` | | **0** |
| `h(b)` | `0 + goal.cost` = 0 + 1 | **1** ← sigue siendo 1 |
| `h(a)` | `h(b) + b.cost` = 1 + 2 | **3** ← aquí aparece el 2 |
| `h(start)` | `h(a) + a.cost` = 3 + 1 | **4** |

Fíjate en que `h(b)` **no** cambió al marcar `b` como `restricted`: el coste de
`b` lo paga quien entra en `b`, o sea `a`. Si en tu implementación `h(b)` sube a
2, estás sumando el coste equivocado. **Este es el test que caza el bug.**

## Paso 4 — La interfaz

`fly_in/pathfinding/abstract_distance.py`

```python
class AbstractDistance:
    """Coste mínimo real de cada zona al objetivo, ignorando otros drones.

    Se calcula una sola vez al arrancar, con un Dijkstra desde end_hub
    recorriendo el grafo hacia atrás. Es admisible: nunca sobreestima, porque
    los demás drones solo pueden hacer que un dron tarde más, nunca menos.
    """

    def __init__(self, graph: Graph) -> None:
        self._dist: dict[str, int] = self._compute(graph)

    def _compute(self, graph: Graph) -> dict[str, int]:
        """Dijkstra desde end_hub. Las zonas 'blocked' no se expanden."""

    def h(self, zone: Zone) -> int:
        """Heurística admisible: turnos mínimos de `zone` al objetivo.

        Raises:
            KeyError: si la zona es inalcanzable desde el objetivo.
        """

    def is_reachable(self, zone: Zone) -> bool:
        """True si existe alguna ruta de `zone` al objetivo."""
```

⚠️ **No lo des por sentado — las zonas inalcanzables NO están en el diccionario**
Una zona rodeada de `blocked`, o desconectada, nunca se visita en el Dijkstra y
por tanto no aparece como clave. Esa **ausencia es la información**: no la
rellenes con `float("inf")`.

Razón concreta: `h(n)` entra en la suma `f = g + h`, y `g + inf` propaga el
infinito por toda tu aritmética de enteros (y rompe `mypy`, que ve un `float`
donde declaraste `int`). Es mucho más limpio preguntar `is_reachable()` antes y
descartar el vecino. Si prefieres un centinela, usa un entero grande pero finito
(`10**9`) y documéntalo.

⚠️ **No lo des por sentado — `h` se indexa por NOMBRE, no por objeto `Zone`**
`Zone` no define `__hash__` ni `__eq__`, así que hashea por identidad. Funciona
mientras solo exista una instancia por zona —que el `Graph` garantiza— pero es
frágil: en cuanto un test construya una `Zone("goal", ...)` nueva, fallará de
forma desconcertante. Indexar por `zone.name` es explícito y a prueba de eso.

## Paso 5 — Reutiliza el Dijkstra de SP04

No copies y pegues el algoritmo. Si tu `Dijkstra` de SP04 expone un método que
calcula la tabla de distancias completa desde un origen (sin parar al encontrar
un objetivo concreto), `AbstractDistance` es un envoltorio de ocho líneas sobre
él.

Si no lo expone, este es el momento de refactorizarlo: extrae un
`_distances_from(origin) -> dict[str, int]` y haz que `find_path()` lo use. Dos
usuarios de la misma lógica es exactamente cuando conviene extraerla — ni antes
(sería especular) ni después (sería duplicar).

---

## Tests de cierre (`test/test_abstract_distance.py`)

- [ ] `h(end_hub) == 0`
- [ ] Mapa lineal `start→a→b→goal` todo `normal`: `h(start) == 3`
- [ ] Con `b` marcada `restricted`: `h(start) == 4` **y `h(b) == 1`** ← el test clave
- [ ] Una zona `blocked` no aparece en el diccionario
- [ ] Una zona aislada (sin conexiones) no aparece en el diccionario
- [ ] `is_reachable()` es `False` para las dos anteriores
- [ ] **Coherencia con SP04:** para cada zona alcanzable del mapa,
      `h(zona) == Dijkstra(graph).cost_of(find_path(zona, end_hub))`

El último es el test definitivo: compara las dos implementaciones entre sí,
zona por zona, en todos los mapas. Si ambas coinciden en todo, o las dos están
bien, o tienen exactamente el mismo bug — y como una va hacia delante y la otra
hacia atrás, eso es muy improbable.

---

## Criterio de salida

- [ ] Los 7 tests pasan, **incluido el de coherencia con Dijkstra**
- [ ] Puedes explicar, sin mirar, por qué al ir hacia atrás se suma el coste del
      nodo que expandes y no el del vecino
- [ ] `make lint-strict` pasa

## Decisiones a anotar

- ¿Cómo representas lo inalcanzable: ausencia de clave, o centinela entero?
- ¿`AbstractDistance` se recalcula alguna vez? *(No: el grafo es inmutable y las
  zonas `blocked` no cambian durante la simulación. Una vez al arrancar, y ya.)*
