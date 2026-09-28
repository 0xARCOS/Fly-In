# Diagramas de flujo del proyecto

Todos los diagramas de lo construido **hasta SP06**, sacados del código real
(no del plan). Hay uno por subproyecto y tres vistas de cómo se relacionan.
Lo que aún no existe (SP07–SP11) aparece con línea discontinua y en gris.

**Cómo leerlos**

| Forma | Significa |
|---|---|
| Rectángulo | Un paso que siempre se ejecuta |
| Rombo | Una decisión (`if`) |
| Estadio `([ ])` | Inicio o fin: lo que devuelve la función |
| Hexágono `{{ }}` | Una excepción que se lanza |
| Línea discontinua `-.->` | Algo que ocurrirá en un subproyecto futuro |

---

## Índice

- [Relación 1 — dependencias entre subproyectos](#relación-1--dependencias-entre-subproyectos)
- [Relación 2 — flujo de datos del programa](#relación-2--flujo-de-datos-del-programa)
- [Relación 3 — dependencias entre módulos](#relación-3--dependencias-entre-módulos-imports)
- [SP00 — Setup y Makefile](#sp00--setup-y-makefile)
- [SP01 — Modelo de dominio](#sp01--modelo-de-dominio)
- [SP02 — Parser](#sp02--parser)
- [SP03 — CLI y errores](#sp03--cli-y-errores)
- [SP04 — Dijkstra](#sp04--dijkstra)
- [SP05 — Heurística abstracta](#sp05--heurística-abstracta)
- [SP06 — Tabla de reservas](#sp06--tabla-de-reservas)

---

## Relación 1 — dependencias entre subproyectos

Una flecha `A → B` significa "B no se puede empezar sin A verde".

```mermaid
flowchart TD
    SP00["SP00 · Setup<br/>Makefile, venv, linters"] --> SP01["SP01 · Modelo<br/>Zone, Connection, Graph"]
    SP01 --> SP02["SP02 · Parser<br/>MapParser"]
    SP02 --> SP03["SP03 · CLI<br/>main.py"]
    SP02 --> SP04["SP04 · Dijkstra<br/>ruta de 1 dron"]
    SP04 --> SP05["SP05 · AbstractDistance<br/>heurística h"]
    SP01 --> SP06["SP06 · ReservationTable<br/>ocupación en el tiempo"]
    SP05 -.-> SP07["SP07 · WhcaPathfinder"]
    SP06 -.-> SP07
    SP07 -.-> SP08["SP08 · Drone + Simulator"]
    SP03 -.-> SP08
    SP08 -.-> SP09["SP09 · OutputFormatter"]
    SP09 -.-> SP10["SP10 · Visualización"]
    SP09 -.-> SP11["SP11 · Benchmarks + README"]
    SP10 -.-> SP11

    classDef done fill:#d5f5d5,stroke:#2e7d32,color:#000
    classDef todo fill:#eeeeee,stroke:#999,color:#555,stroke-dasharray:4
    class SP00,SP01,SP02,SP03,SP04,SP05,SP06 done
    class SP07,SP08,SP09,SP10,SP11 todo
```

**Lo que hay que ver aquí:**
- Tras el parser el trabajo se abre en **dos ramas independientes**: la del
  algoritmo (SP04 → SP05) y la de la ocupación (SP06, que solo necesita el
  modelo). SP07 es el primer punto donde se juntan.
- SP03 (CLI) no lo necesita nadie hasta SP08, que es cuando el programa
  empieza a simular de verdad.

---

## Relación 2 — flujo de datos del programa

Qué recorre un mapa desde el archivo hasta la pantalla. Verde: lo que ya pasa
hoy al ejecutar `make run`. Gris: lo que se añadirá.

```mermaid
flowchart LR
    F[/"maps/x.txt"/] --> R["read_map_file<br/>SP03"]
    R -->|"texto"| P["MapParser.parse<br/>SP02"]
    P -->|"nb_drones, Graph"| AD["AbstractDistance<br/>SP05<br/>1 vez al arrancar"]
    AD -->|"¿end alcanzable?"| M["main: resumen<br/>SP03"]
    M --> OUT[/"stdout"/]
    AD --> DJ["Dijkstra.distances_from<br/>SP04"]

    P -.->|"Graph"| RT["ReservationTable<br/>SP06"]
    AD -.->|"h de cada zona"| W["WhcaPathfinder<br/>SP07"]
    RT -.->|"can_move, zone_has_room"| W
    W -.->|"reserve_move, reserve_wait"| RT
    W -.->|"rutas"| S["Simulator<br/>SP08"]
    S -.->|"clear_from cada W/2"| RT
    S -.->|"movimientos"| O["OutputFormatter<br/>SP09"]
    S -.-> V["TerminalRenderer<br/>SP10"]
    O -.-> OUT

    classDef done fill:#d5f5d5,stroke:#2e7d32,color:#000
    classDef todo fill:#eeeeee,stroke:#999,color:#555,stroke-dasharray:4
    class R,P,AD,M,DJ done
    class RT,W,S,O,V todo
```

**Lo que hay que ver aquí:**
- El parser y la heurística corren **una sola vez**. Lo que se repite en
  bucle (a partir de SP07/SP08) es el ciclo tabla ⇄ buscador ⇄ simulador.
- `ReservationTable` (SP06) ya existe y está probada, pero todavía nadie la
  usa desde `main`: su primer cliente será SP07.

---

## Relación 3 — dependencias entre módulos (imports)

Quién importa a quién, verificado con `grep` sobre el código. Las flechas van
de "el que importa" a "el importado": ninguna vuelve hacia arriba, así que no
hay dependencias circulares.

```mermaid
flowchart TD
    main["main.py<br/>SP03"]
    parser["parsing/map_parser.py<br/>SP02"]
    dijkstra["pathfinding/dijkstra.py<br/>SP04"]
    heur["pathfinding/abstract_distance.py<br/>SP05"]
    table["pathfinding/reservation_table.py<br/>SP06"]
    graph["models/graph.py"]
    conn["models/connection.py"]
    zone["models/zone.py"]
    errors["models/errors.py"]

    main --> parser
    main --> heur
    main --> errors
    parser --> graph
    parser --> zone
    parser --> errors
    heur --> dijkstra
    heur --> graph
    heur --> zone
    dijkstra --> graph
    dijkstra --> zone
    table --> graph
    table --> conn
    table --> zone
    graph --> conn
    graph --> zone
    conn --> zone
```

**Lo que hay que ver aquí:**
- `models/` no importa nada de fuera de `models/`: el dominio no sabe que
  existen el parser ni el pathfinding. Por eso se puede testear solo.
- `reservation_table.py` no importa `dijkstra` ni `abstract_distance`: SP06 es
  independiente de SP04/SP05, igual que en la Relación 1.

---

## SP00 — Setup y Makefile

Qué hace cada regla del `Makefile`.

```mermaid
flowchart TD
    subgraph INSTALL["make install"]
        I1["python3 -m venv .venv"] --> I2["pip install --upgrade pip"] --> I3["pip install -e .[dev]<br/>flake8, mypy, pytest"]
    end
    subgraph RUN["make run / make debug"]
        R1["python -m fly_in.main MAP"]
        R2["python -m pdb -m fly_in.main MAP"]
    end
    subgraph LINT["make lint / make lint-strict"]
        L1["flake8 ."] --> L2{"¿strict?"}
        L2 -->|"no"| L3["mypy . con los flags del subject"]
        L2 -->|"sí"| L4["mypy . --strict"]
    end
    subgraph CLEAN["make clean / make fclean"]
        C1["borra .mypy_cache, .pytest_cache,<br/>*.egg-info y __pycache__<br/>sin entrar en .venv"] --> C2{"¿fclean?"}
        C2 -->|"sí"| C3["borra también .venv"]
        C2 -->|"no"| C4(["la venv se conserva"])
    end
    T["make test → pytest"]
```

**Por qué `clean` no borra `.venv`:** el subject dice que `clean` borra
archivos temporales y cachés. El entorno no es temporal: borrarlo obliga a
reinstalar. Para eso existe `fclean`.

---

## SP01 — Modelo de dominio

### `Graph.add_zone(zone, role)`

```mermaid
flowchart TD
    A(["add_zone(zone, role)"]) --> B{"¿role es hub,<br/>start_hub o end_hub?"}
    B -->|"no"| E1{{"ValueError<br/>Unknown zone role"}}
    B -->|"sí"| C{"¿nombre ya usado?"}
    C -->|"sí"| E2{{"ValueError<br/>already defined"}}
    C -->|"no"| D{"¿role?"}
    D -->|"start_hub"| D1{"¿ya hay start_hub?"}
    D1 -->|"sí"| E3{{"ValueError<br/>Only one start_hub"}}
    D1 -->|"no"| D2["graph.start_hub = zone"]
    D -->|"end_hub"| D3{"¿ya hay end_hub?"}
    D3 -->|"sí"| E4{{"ValueError<br/>Only one end_hub"}}
    D3 -->|"no"| D4["graph.end_hub = zone"]
    D -->|"hub"| F
    D2 --> F["zones[nombre] = zone<br/>adjacency[nombre] = lista vacía"]
    D4 --> F
    F --> G(["fin"])
```

### `Graph.add_connection(origin, destination, capacidad)`

```mermaid
flowchart TD
    A(["add_connection(a, b, cap)"]) --> B{"¿a existe?"}
    B -->|"no"| E1{{"ValueError<br/>undefined zone"}}
    B -->|"sí"| C{"¿b existe?"}
    C -->|"no"| E1
    C -->|"sí"| D["pair = frozenset(a, b)<br/>a-b y b-a dan la misma clave"]
    D --> F{"¿pair ya está<br/>en by_pair?"}
    F -->|"sí"| E2{{"ValueError<br/>Duplicate connection"}}
    F -->|"no"| G["crea Connection(zona a, zona b, cap)"]
    G --> H["connections.append<br/>by_pair[pair] = conn<br/>adjacency[a].append<br/>adjacency[b].append"]
    H --> I(["fin"])
```

### Las dos consultas O(1)

```mermaid
flowchart LR
    N(["neighbors(zone)"]) --> N1["adjacency[zone.name]"] --> N2(["copia de la lista<br/>en orden de definición"])
    CB(["connection_between(a, b)"]) --> CB1{"¿frozenset(a, b)<br/>en by_pair?"}
    CB1 -->|"sí"| CB2(["esa Connection"])
    CB1 -->|"no"| CB3{{"ValueError<br/>No connection"}}
```

### Métodos de `Zone` y `Connection`

```mermaid
flowchart TD
    T(["zone.is_traversable()"]) --> T1(["zone_type is not BLOCKED"])
    MC(["zone.movement_cost()"]) --> MC1{"¿traversable?"}
    MC1 -->|"no"| MC2{{"ValueError<br/>blocked zone"}}
    MC1 -->|"sí"| MC3(["NORMAL 1 · PRIORITY 1 · RESTRICTED 2"])
    OE(["conn.other_end(zone)"]) --> OE1{"¿zone es zone_a?"}
    OE1 -->|"sí"| OE2(["zone_b"])
    OE1 -->|"no"| OE3{"¿zone es zone_b?"}
    OE3 -->|"sí"| OE4(["zone_a"])
    OE3 -->|"no"| OE5{{"ValueError<br/>not part of this connection"}}
```

**Por qué las reglas viven en `Graph` y no en el parser:** el parser mira una
línea cada vez y no recuerda las anteriores. `Graph` sí lo sabe todo, así que
es imposible construir un grafo inválido venga de donde venga (parser, test o
intérprete).

---

## SP02 — Parser

### `MapParser.parse(texto)`: el archivo entero

```mermaid
flowchart TD
    A(["parse(texto)"]) --> B["clean_lines: quita los comentarios,<br/>strip, descarta vacías,<br/>guarda el nº de línea original"]
    B --> C{"¿queda alguna línea?"}
    C -->|"no"| E0{{"MapValidationError<br/>Map file is empty"}}
    C -->|"sí"| D{"¿la primera empieza<br/>por nb_drones: ?"}
    D -->|"no"| E1{{"MapParseError línea N<br/>First line must define nb_drones"}}
    D -->|"sí"| F["parse_positive_int"]
    F -->|"no es entero mayor que 0"| E2{{"MapParseError línea N"}}
    F -->|"ok"| G["graph = Graph()"]
    G --> H{"¿quedan líneas?"}
    H -->|"sí"| I["_parse_line(línea, graph)"]
    I -->|"ValueError"| E3{{"MapParseError<br/>con nº de línea, texto y causa"}}
    I -->|"ok"| H
    H -->|"no"| J{"¿hay start_hub?"}
    J -->|"no"| E4{{"MapValidationError<br/>needs a start_hub"}}
    J -->|"sí"| K{"¿hay end_hub?"}
    K -->|"no"| E5{{"MapValidationError<br/>needs an end_hub"}}
    K -->|"sí"| L(["devuelve nb_drones, graph"])
```

**Por qué dos excepciones distintas:** `MapParseError` señala **una línea**
concreta. `MapValidationError` es un fallo del archivo **en conjunto** (vacío,
falta el start…): no hay una línea a la que apuntar. Las dos heredan de
`MapError`, que es lo único que captura `main`.

### `_parse_line`: una línea de zona o de conexión

```mermaid
flowchart TD
    A(["_parse_line(línea)"]) --> B{"¿empieza por<br/>connection: ?"}
    B -->|"sí"| C["parse_connection_line<br/>→ origen, destino, metadatos"]
    C --> C1["max_link_capacity = parse_positive_int<br/>por defecto 1"]
    C1 --> C2["graph.add_connection"]
    C2 --> Z(["fin"])
    B -->|"no"| D{"¿lo de antes de ':' es<br/>hub, start_hub o end_hub?"}
    D -->|"no"| E1{{"ValueError<br/>Unknown directive"}}
    D -->|"sí"| E["parse_zone_line<br/>→ rol, nombre, x, y, metadatos"]
    E --> F["zone_type = parse_zone_type<br/>por defecto normal"]
    F --> G{"¿rol es start_hub<br/>o end_hub?"}
    G -->|"sí"| G1["max_drones = UNLIMITED<br/>se ignora lo que diga el archivo"]
    G1 --> G2{"¿zone_type BLOCKED?"}
    G2 -->|"sí"| E2{{"ValueError<br/>can't be a blocked zone"}}
    G2 -->|"no"| H
    G -->|"no"| G3["max_drones = parse_positive_int<br/>por defecto 1"]
    G3 --> H["graph.add_zone(Zone, rol)"]
    H --> Z
```

### `parse_zone_line` y `parse_connection_line`

```mermaid
flowchart TD
    subgraph ZL["parse_zone_line"]
        Z1["parte por el primer ':' → rol, resto"] --> Z2{"¿hay '[' en el resto?"}
        Z2 -->|"sí"| Z3["parse_metadata del bloque,<br/>claves permitidas: zone, color, max_drones"]
        Z2 -->|"no"| Z4
        Z3 --> Z4{"¿exactamente 3 campos:<br/>nombre x y?"}
        Z4 -->|"no"| ZE1{{"ValueError"}}
        Z4 -->|"sí"| Z5{"¿nombre contiene '-'?"}
        Z5 -->|"sí"| ZE2{{"ValueError"}}
        Z5 -->|"no"| Z6{"¿x e y son enteros?<br/>negativos permitidos"}
        Z6 -->|"no"| ZE3{{"ValueError"}}
        Z6 -->|"sí"| Z7(["rol, nombre, x, y, metadatos"])
    end
    subgraph CL["parse_connection_line"]
        C1["cuerpo tras 'connection:'"] --> C2{"¿hay '['?"}
        C2 -->|"sí"| C3["parse_metadata,<br/>clave permitida: max_link_capacity"]
        C2 -->|"no"| C4
        C3 --> C4{"¿partido por '-' da<br/>exactamente 2 trozos?"}
        C4 -->|"no"| CE1{{"ValueError"}}
        C4 -->|"sí"| C5{"¿algún nombre vacío?"}
        C5 -->|"sí"| CE2{{"ValueError"}}
        C5 -->|"no"| C6{"¿origen igual a destino?"}
        C6 -->|"sí"| CE3{{"ValueError"}}
        C6 -->|"no"| C7(["origen, destino, metadatos"])
    end
```

### `parse_metadata`: validación estricta de `[k=v ...]`

```mermaid
flowchart TD
    A(["parse_metadata(bloque, claves_permitidas)"]) --> B{"¿empieza por '['<br/>y acaba en ']'?"}
    B -->|"no"| E1{{"ValueError<br/>must be wrapped"}}
    B -->|"sí"| C{"¿quedan tokens?"}
    C -->|"no"| Z(["diccionario"])
    C -->|"sí"| D["token.partition('=')"]
    D --> F{"¿hay '=', clave<br/>no vacía y valor no vacío?"}
    F -->|"no"| E2{{"ValueError<br/>expected key=value"}}
    F -->|"sí"| G{"¿clave permitida<br/>en este tipo de línea?"}
    G -->|"no"| E3{{"ValueError<br/>Unknown metadata key"}}
    G -->|"sí"| H{"¿clave repetida?"}
    H -->|"sí"| E4{{"ValueError<br/>Duplicate metadata key"}}
    H -->|"no"| I["guarda clave → valor"]
    I --> C
```

**Por qué rechazar claves repetidas:** `[zone=blocked zone=normal]` haría la
zona transitable en silencio (gana la última). El subject exige metadatos
*"syntactically valid"*, y es mejor un error claro que un mapa que no hace lo
que parece.

---

## SP03 — CLI y errores

`main()` es la **frontera de excepciones**: ningún error de mapa sale como
traceback.

```mermaid
flowchart TD
    A(["python -m fly_in.main mapa --window W"]) --> B["argparse"]
    B --> B1{"¿argumentos válidos?<br/>window entero mayor que 0"}
    B1 -->|"no"| X2(["argparse imprime el uso<br/>código 2"])
    B1 -->|"sí"| C["read_map_file"]
    C --> C1{"¿existe? ¿no es carpeta?<br/>¿permiso? ¿UTF-8?"}
    C1 -->|"no"| ERR
    C1 -->|"sí"| D["MapParser.parse"]
    D -->|"MapParseError o<br/>MapValidationError"| ERR
    D -->|"ok"| E["AbstractDistance(graph)"]
    E --> F{"¿start_hub puede<br/>llegar a end_hub?"}
    F -->|"no"| E1["lanza MapValidationError<br/>unreachable"] --> ERR
    F -->|"sí"| G["imprime el resumen<br/>provisional hasta SP08"]
    G --> OK(["código 0"])
    ERR["captura MapError:<br/>'Error: …' por stderr"] --> X1(["código 1"])
    A -.->|"Ctrl+C"| KI(["'Interrupted by user.'<br/>código 130"])
    G -.->|"SP08"| SIM["Simulator.run"]

    classDef todo fill:#eeeeee,stroke:#999,color:#555,stroke-dasharray:4
    class SIM todo
```

**Por qué comprobar la alcanzabilidad aquí y no en SP08:** sin esta
comprobación, un mapa sin ruta posible haría que el simulador diera vueltas
hasta su límite de seguridad. Aquí se detecta al instante, con un mensaje que
dice exactamente qué pasa.

---

## SP04 — Dijkstra

### `find_path(origin, target)`: la ruta de un dron

```mermaid
flowchart TD
    A(["find_path(origen, destino)"]) --> B{"¿origen o destino<br/>BLOCKED?"}
    B -->|"sí"| N(["None"])
    B -->|"no"| C{"¿origen igual a destino?"}
    C -->|"sí"| C1(["lista con solo el origen"])
    C -->|"no"| D["heap = coste 0, -prio, contador, origen<br/>dist[origen] = 0, -prio<br/>visited = vacío"]
    D --> E{"¿heap vacío?"}
    E -->|"sí"| N
    E -->|"no"| F["saca el menor:<br/>1º coste, 2º más zonas priority,<br/>3º contador"]
    F --> G{"¿ya visitada?"}
    G -->|"sí"| E
    G -->|"no"| H["marca visitada"]
    H --> I{"¿es el destino?"}
    I -->|"sí"| R(["reconstruye la ruta<br/>siguiendo prev hacia atrás"])
    I -->|"no"| J["para cada conexión en<br/>graph.neighbors(actual)"]
    J --> K{"¿vecino BLOCKED?"}
    K -->|"sí"| J
    K -->|"no"| L["nuevo = coste + vecino.movement_cost()<br/>nueva_prio = prio - 1 si es PRIORITY"]
    L --> M{"¿vecino sin dist, o nuevo, nueva_prio<br/>mejor que dist[vecino]?"}
    M -->|"no"| J
    M -->|"sí"| O["dist[vecino] = nuevo<br/>prev[vecino] = actual<br/>push al heap"]
    O --> J
    J -->|"sin más conexiones"| E
```

**Por qué la clave es una tupla de tres:** `priority` cuesta lo mismo que
`normal`, así que la preferencia no puede ir en el coste sin romper "coste =
turnos". Va como **desempate**: Python compara tuplas elemento a elemento. El
contador final evita comparar dos `Zone`, que daría `TypeError`.

### `distances_from(origin, reverse)`: coste a todas las zonas

```mermaid
flowchart TD
    A(["distances_from(origen, reverse)"]) --> B{"¿origen BLOCKED?"}
    B -->|"sí"| V(["diccionario vacío"])
    B -->|"no"| C["dist[origen] = 0<br/>heap con el origen"]
    C --> D{"¿heap vacío?"}
    D -->|"sí"| R(["dist: nombre → coste mínimo"])
    D -->|"no"| E["saca el de menor coste"]
    E --> F{"¿coste mayor que dist[actual]?<br/>entrada obsoleta"}
    F -->|"sí"| D
    F -->|"no"| G["para cada vecino no BLOCKED"]
    G --> H{"¿reverse?"}
    H -->|"no, hacia delante"| H1["paso = vecino.movement_cost()<br/>coste de entrar en el vecino"]
    H -->|"sí, hacia atrás"| H2["paso = actual.movement_cost()<br/>coste de entrar en la zona de la que<br/>venimos, recorriendo al revés"]
    H1 --> I{"¿nuevo coste mejor?"}
    H2 --> I
    I -->|"sí"| J["actualiza dist y push"] --> G
    I -->|"no"| G
    G -->|"sin más vecinos"| D
```

**Por qué `reverse` suma el coste de `actual`:** el coste depende de la zona en
la que **entras**. Al recorrer desde `end_hub` hacia atrás, el paso de `vecino`
a `actual` en la ruta real es entrar en `actual`. Sumar el del vecino daría
costes desplazados una zona.

---

## SP05 — Heurística abstracta

```mermaid
flowchart TD
    A(["AbstractDistance(graph)"]) --> B{"¿graph.end_hub existe?"}
    B -->|"no"| B1["tabla vacía"]
    B -->|"sí"| C["Dijkstra(graph).distances_from(<br/>end_hub, reverse=True)"]
    C --> D["_dist: nombre → turnos mínimos<br/>de esa zona a end_hub"]
    D --> Q1(["h(zona)"])
    Q1 --> Q2{"¿zona en _dist?"}
    Q2 -->|"sí"| Q3(["_dist[zona]"])
    Q2 -->|"no"| Q4{{"KeyError"}}
    D --> R1(["is_reachable(zona)"]) --> R2(["zona in _dist"])
```

**Por qué una sola ejecución desde `end_hub` y no una por zona:** un Dijkstra
hacia atrás da de golpe la distancia real de **todas** las zonas al objetivo.
Lanzar uno desde cada zona costaría `V` veces más.

**Por qué no la distancia en línea recta entre coordenadas:** ignora las zonas
`blocked` y los callejones sin salida. La de Dijkstra es la real sin otros
drones: nunca sobreestima (es admisible) y conoce la topología.

**Por qué las inalcanzables no están en la tabla:** su ausencia **es** la
información. Guardarlas como `inf` metería un `float` en una suma de enteros
(`f = g + h`) y rompería mypy.

---

## SP06 — Tabla de reservas

### La convención de tiempo

```mermaid
flowchart LR
    I0(["instante 0<br/>todos en start"]) -->|"turno 1<br/>línea 1 de la salida"| I1(["instante 1"])
    I1 -->|"turno 2<br/>línea 2"| I2(["instante 2"])
    I2 -->|"turno 3<br/>línea 3"| I3(["instante 3"])
```

- Zona `(z, t)` = quién está en `z` **en la foto** `t`.
- Conexión `(c, t)` = quién está cruzando `c` **entre** la foto `t` y la `t+1`.

### Qué ocupa un movimiento que sale en el instante T

```mermaid
flowchart LR
    subgraph N["coste 1: normal o priority"]
        direction LR
        n0["T<br/>en origen<br/>conexión ✔"] --> n1["T+1<br/>en destino"]
    end
    subgraph R["coste 2: restricted"]
        direction LR
        r0["T<br/>en origen<br/>conexión ✔"] --> r1["T+1<br/>EN EL AIRE<br/>conexión ✔<br/>ninguna zona"] --> r2["T+2<br/>en destino"]
    end
```

### `can_move(frm, to, turn)`: la pregunta completa

```mermaid
flowchart TD
    A(["can_move(frm, to, T)"]) --> B["conn = graph.connection_between(frm, to)"]
    B -->|"no conectadas"| E{{"ValueError"}}
    B --> C{"¿to es BLOCKED?"}
    C -->|"sí"| F(["False"])
    C -->|"no"| D["cost = to.movement_cost()"]
    D --> G["para cada slot de T a T+cost-1"]
    G --> H{"¿cabe en la conexión<br/>en ese slot?"}
    H -->|"no"| F
    H -->|"sí"| I{"¿alguien va en sentido<br/>to → frm en ese slot?"}
    I -->|"sí, se cruzarían"| F
    I -->|"no"| G
    G -->|"todos los slots libres"| J{"¿cabe en la zona to<br/>en el instante T+cost?"}
    J -->|"no"| F
    J -->|"sí"| K(["True"])
```

**Por qué una sola función:** comprueba las tres cosas que ocupa un movimiento
(conexión, sentido y zona de llegada) en **todos** los instantes del trayecto.
Si SP07 hiciera las comprobaciones sueltas, podría olvidar una o comprobar solo
el primer instante de un tránsito `restricted`.

### `reserve_move` y `reserve_wait`: escribir sin dejar nada a medias

```mermaid
flowchart TD
    subgraph RM["reserve_move(id, frm, to, T)"]
        M1{"¿can_move(frm, to, T)?"} -->|"no"| ME{{"ReservationError<br/>no se ha tocado nada"}}
        M1 -->|"sí"| M2["para cada slot de T a T+cost-1:<br/>links[conn, slot] += id<br/>moves[frm, to, slot] += id"]
        M2 --> M3["zones[to, T+cost] += id"]
        M3 --> M4(["fin"])
    end
    subgraph RW["reserve_wait(id, zona, t)"]
        W1{"¿zone_has_room(zona, t)?"} -->|"no"| WE{{"ReservationError"}}
        W1 -->|"sí"| W2["zones[zona, t] += id"] --> W3(["fin"])
    end
    subgraph ADD["_add(tabla, clave, id), usado por ambos"]
        A1{"¿id ya está en esa clave?"} -->|"sí"| AE{{"ReservationError<br/>ya reservado"}}
        A1 -->|"no"| A2["añade id"]
    end
```

**Por qué primero pregunta y después escribe:** si escribiera la conexión y
luego descubriera que la zona de llegada está llena, quedaría una conexión
ocupada por un movimiento que nunca ocurre. Los demás drones esquivarían un
fantasma.

### `clear_from(turn, keep)`: replanificar

```mermaid
flowchart TD
    A(["clear_from(T, keep)"]) --> B["para zones, links y moves:<br/>construye un diccionario nuevo"]
    B --> C{"para cada clave:<br/>¿su instante es menor que T?"}
    C -->|"sí, es pasado"| D["se conserva entera"]
    C -->|"no, es futuro"| E["se conservan solo los ids<br/>que están en keep"]
    E --> F{"¿queda algún id?"}
    F -->|"sí"| G["se guarda la clave"]
    F -->|"no"| H["la clave desaparece"]
    D --> Z(["la tabla nueva sustituye a la vieja"])
    G --> Z
    H --> Z
```

### Por qué existe `keep`: un dron en el aire al replanificar

```mermaid
sequenceDiagram
    participant S as Simulator (SP08)
    participant T as ReservationTable
    participant D1 as D1 (en el aire)
    participant D2 as D2
    Note over D1: instante 4: despega hacia r (restricted)
    D1->>T: reserve_move(1, start, r, 4)<br/>conexión en 4 y 5, r en 6
    Note over S: instante 5: toca replanificar
    S->>T: clear_from(5, keep={1})
    Note over T: se borra el futuro de todos<br/>salvo D1: conexión en 5 y r en 6 siguen
    S->>D2: replanifica
    D2->>T: can_move(start, r, 5)?
    T-->>D2: False: conexión ocupada y r reservada en 6
    Note over D1: instante 6: aterriza en r con sitio garantizado
```

Sin `keep`, `clear_from(5)` borraría la llegada de D1. D2 podría ocupar `r` en
el 6, y D1 no tendría dónde aterrizar ni podría esperar en el aire.

### Cómo usarán SP07 y SP08 la tabla (futuro)

```mermaid
flowchart TD
    S0["Simulator, cada W/2 turnos"] -.-> S1["clear_from(T, keep = drones en el aire)"]
    S1 -.-> S2["para cada dron, en orden de prioridad"]
    S2 -.-> W1["WhcaPathfinder.find_path"]
    W1 -.->|"expande vecinos"| Q1["can_move(zona, vecino, t)"]
    W1 -.->|"expande 'esperar'"| Q2["zone_has_room(zona, t+1)"]
    W1 -.->|"ruta elegida"| R1["reserve_move / reserve_wait<br/>con el id del dron"]
    R1 -.-> S2

    classDef todo fill:#eeeeee,stroke:#999,color:#555,stroke-dasharray:4
    class S0,S1,S2,W1,Q1,Q2,R1 todo
```
