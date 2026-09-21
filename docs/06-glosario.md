# Glosario

Todos los términos que aparecen en la guía, en el código y en el subject,
definidos sin dar nada por sabido. Si en algún subproyecto te encuentras una
palabra que no tienes clarísima, está aquí.

---

## Términos del dominio (el problema)

**Zona (`Zone`)**
Un nodo del grafo. Tiene nombre único, coordenadas enteras `x`/`y`, un tipo
(`normal`/`priority`/`restricted`/`blocked`), una capacidad `max_drones` y un
color opcional. Las coordenadas **no definen adyacencia**, solo sirven para
dibujar.

**Conexión (`Connection`)**
Una arista **bidireccional** entre dos zonas. Tiene `max_link_capacity`: cuántos
drones la pueden atravesar a la vez. En el archivo de mapa se escribe
`connection: a-b`, y `a-b` y `b-a` son la misma conexión.

**`start_hub` / `end_hub`**
Las dos zonas especiales, exactamente una de cada. Todos los drones empiezan en
`start_hub` y la simulación acaba cuando todos han llegado a `end_hub`. **Ni una
ni otra tienen límite de capacidad**, y su `max_drones` se ignora.

**`hub`**
El prefijo de una zona normal en el archivo de mapa. No confundir con
`start_hub`/`end_hub`: `hub:` declara una zona corriente.

**Dron (`Drone`)**
Un agente que se mueve por el grafo. Tiene un ID entero (que aparece como `D1`,
`D2`… en la salida), una posición actual y una ruta planificada.

**Turno**
La unidad de tiempo de la simulación. Discreta: turno 0, 1, 2… En cada turno,
cada dron se mueve a una zona adyacente, entra en una conexión hacia una
`restricted`, o se queda quieto. Todos los drones actúan **simultáneamente**.

**Entregado (*delivered*)**
Un dron que ha llegado a `end_hub`. Deja de rastrearse y no vuelve a aparecer en
la salida.

**En tránsito (*in transit*)**
El estado de un dron que ha entrado en una conexión hacia una zona `restricted`
y aún no ha llegado. Dura exactamente un turno intermedio, durante el cual el
dron **ocupa la conexión pero ninguna zona**. No puede detenerse ahí.

**Capacidad (`max_drones`, `max_link_capacity`)**
Cuántos drones caben simultáneamente en una zona / en una conexión. Por defecto
1 en ambos casos.

**Cuello de botella (*bottleneck*)**
Un punto del grafo por el que toda ruta debe pasar y cuya capacidad es menor que
el número de drones. Obliga a que los drones se alternen y es donde se ve si tu
coordinación funciona o no. `maps/valid/bottleneck.txt` es exactamente esto.

**Deadlock**
Situación en la que dos o más drones se bloquean mutuamente de forma
indefinida: A espera a que B se aparte, B espera a que A se aparte. Ninguno
avanza nunca. Ver por qué WHCA\* lo evita sin código especial en
[`04-algoritmo.md`](./04-algoritmo.md).

---

## Términos de algoritmia

**Grafo**
Conjunto de nodos (zonas) y aristas (conexiones). Aquí es **no dirigido** (las
conexiones van en los dos sentidos) y **ponderado** (cada movimiento tiene un
coste en turnos).

**Dijkstra**
Algoritmo de camino de coste mínimo desde un origen a todos los demás nodos,
para grafos con pesos no negativos. Usa una **cola de prioridad**: siempre
expande el nodo no visitado más barato conocido.

**Cola de prioridad / heap (`heapq`)**
Estructura que siempre te da el elemento **mínimo** en `O(log n)`. En Python es
`heapq` sobre una lista: `heappush(h, item)` y `heappop(h)`. El "mínimo" se
decide comparando los elementos, y por eso se meten **tuplas**: se comparan
elemento a elemento, de izquierda a derecha.

**A\***
Dijkstra más una **heurística**: en vez de expandir por `g` (coste gastado),
expande por `f = g + h`, donde `h` estima lo que queda. Si `h` es buena, explora
muchísimos menos nodos que Dijkstra para el mismo resultado.

**Heurística `h(n)`**
Una estimación del coste desde el nodo `n` hasta el objetivo.

**Admisible**
Una heurística es admisible si **nunca sobreestima** el coste real que queda.
Es la condición para que A\* encuentre la ruta óptima. La distancia real por el
grafo ignorando a los demás drones es admisible por definición: los otros drones
solo pueden hacerte tardar más, nunca menos.

**Heurística abstracta**
La que usamos: el coste real mínimo de cada zona al objetivo, **ignorando a los
demás drones**, precalculada con un Dijkstra desde `end_hub` hacia atrás. Ver
[SP05](./build/SP05-heuristica-abstracta.md).

**Espacio-tiempo**
El espacio de búsqueda donde un estado no es `zona` sino `(zona, turno)`. Es la
idea central de todo el proyecto: convierte "hay otro dron aquí ahora mismo" en
un obstáculo que la búsqueda esquiva sola.

**MAPF (*Multi-Agent Path Finding*)**
La familia de problemas a la que pertenece este proyecto: encontrar rutas para N
agentes que no colisionen. Resolverlo óptimamente es NP-difícil.

**CA\* / HCA\* / WHCA\***
Los tres escalones del paper de Silver (2005). CA\* = A\* en espacio-tiempo con
tabla de reservas. HCA\* = CA\* + heurística abstracta. WHCA\* = HCA\* + ventana
temporal. Implementamos el tercero.

**Ventana (`W`)**
Cuántos turnos hacia el futuro coopera cada dron. Dentro de la ventana consulta
y respeta la tabla de reservas; más allá, confía en la heurística. Se replanifica
cada `W/2` turnos.

**Tabla de reservas (`ReservationTable`)**
El registro de qué `(zona, turno)` y qué `(conexión, turno)` están ocupados y por
cuántos drones. Es lo que permite a un dron ver el futuro de los que planificaron
antes que él.

**Replanificación (*replanning*)**
Recalcular las rutas de todos los drones desde el turno actual, con la tabla de
reservas al día. Es lo que deshace los bloqueos en WHCA\*.

**Receding horizon**
El principio de control del que viene la ventana: planificas un horizonte de `W`,
ejecutas solo la primera mitad, y vuelves a planificar. Así siempre tienes
margen de reacción por delante.

**Optimalidad / completitud**
*Óptimo* = encuentra la mejor solución posible. *Completo* = si existe solución,
la encuentra. WHCA\* **no es ninguna de las dos**, y saber por qué es parte de lo
que se evalúa.

**Nodo cerrado (*closed set*)**
Los estados ya expandidos, que no se vuelven a procesar. En este proyecto la
clave del conjunto de cerrados es `(zona, turno)`, **no** `zona`.

**Desempate (*tie-breaking*)**
Cómo decides entre dos opciones de coste idéntico. Aquí tiene dos usos: preferir
zonas `priority`, y garantizar que el heap nunca intente comparar objetos
`Zone`.

---

## Términos de herramientas y Python

**`mypy`**
Verificador de tipos estático. Lee tus anotaciones (`def f(x: int) -> str:`) y
detecta incoherencias sin ejecutar el código. Obligatorio en este proyecto.

**`--strict`**
El modo más exigente de `mypy`: exige anotar absolutamente todo, incluidos los
`-> None` de los `__init__`. `make lint-strict` lo ejecuta.

**`flake8`**
Comprobador de estilo (PEP 8): longitud de línea, espacios, imports sin usar.
Obligatorio. Su configuración vive en `.flake8` porque flake8 no lee
`pyproject.toml` de forma nativa.

**Type hint / anotación de tipo**
`def parse(content: str) -> tuple[int, Graph]:`. No cambia la ejecución; es
información para `mypy`, para tu editor y para quien lee el código.

**Entorno virtual (`venv`)**
Una instalación de Python aislada dentro de `.venv/`, con sus propias
dependencias. Evita que los paquetes de este proyecto choquen con los de otro.
`make install` lo crea.

**Instalación editable (`pip install -e`)**
Instala el paquete enlazando al código fuente en vez de copiarlo. Editas
`fly_in/` y el cambio aplica al instante, sin reinstalar.

**`pyproject.toml`**
El archivo estándar de metadatos de un proyecto Python: nombre, versión,
dependencias, configuración de herramientas. Sustituye a `setup.py` +
`requirements.txt`.

**Docstring**
La cadena de documentación justo debajo de un `def` o `class`. El subject exige
docstrings estilo PEP 257 *(Cap. III.1)*: qué hace, qué parámetros recibe, qué
devuelve.

**Dataclass**
Un decorador (`@dataclass`) que genera `__init__`, `__repr__` y comparadores a
partir de las anotaciones de atributos. Con `order=True` genera además los
operadores de comparación, que es lo que permite meter el objeto directamente en
un `heapq`. Se usa en [SP07](./build/SP07-whca.md).

**`frozen=True`**
Hace una dataclass inmutable. Como efecto secundario la vuelve *hasheable*, o
sea, utilizable como clave de diccionario o elemento de un `set`.

**Traceback**
El volcado de pila que Python imprime ante una excepción no capturada. Que el
evaluador vea uno significa proyecto no funcional *(Cap. III.1)* — por eso
[SP03](./build/SP03-cli-y-errores.md) existe.
