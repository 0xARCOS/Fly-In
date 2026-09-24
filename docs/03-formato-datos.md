# Formato de datos — entrada y salida

Especificación completa de los dos formatos con los que habla el programa: el
archivo de mapa que lee y las líneas de simulación que escribe.

---

## Parte 1 — El archivo de mapa

### Ejemplo canónico (el del subject, Cap. VI)

```
nb_drones: 5

start_hub: hub 0 0 [color=green]
end_hub: goal 10 10 [color=yellow]
hub: roof1 3 4 [zone=restricted color=red]
hub: roof2 6 2 [zone=normal color=blue]
hub: corridorA 4 3 [zone=priority color=green max_drones=2]
hub: tunnelB 7 4 [zone=normal color=red]
hub: obstacleX 5 5 [zone=blocked color=gray]
connection: hub-roof1
connection: hub-corridorA
connection: roof1-roof2
connection: roof2-goal
connection: corridorA-tunnelB [max_link_capacity=2]
connection: tunnelB-goal
```

### Gramática

```
archivo        ::= linea_drones (zona | conexion | comentario | vacía)*
linea_drones   ::= "nb_drones:" WS entero_positivo
zona           ::= rol ":" WS nombre WS entero WS entero WS metadata? comentario?
rol            ::= "start_hub" | "end_hub" | "hub"
conexion       ::= "connection:" WS nombre "-" nombre WS metadata? comentario?
metadata       ::= "[" (par (WS par)*)? "]"
par            ::= clave "=" valor          # sin espacios alrededor del '='
nombre         ::= caracter+                # sin guiones ni espacios
comentario     ::= "#" cualquier_texto      # hasta el final de la línea
```

### Claves de metadatos y valores por defecto

| Clave | Dónde | Valores | Por defecto | Notas |
|---|---|---|---|---|
| `zone` | zonas | `normal` \| `restricted` \| `priority` \| `blocked` | `normal` | Cualquier otro valor es **error** |
| `color` | zonas | cualquier palabra suelta (`red`, `gray`, `#ff0000`…) | ninguno | **No hay lista fija de colores permitidos** *(Cap. VI)* |
| `max_drones` | zonas | entero positivo | `1` | **Ignorado** en `start_hub` y `end_hub` |
| `max_link_capacity` | conexiones | entero positivo | `1` | |

- Las etiquetas dentro de los corchetes **pueden ir en cualquier orden**.
- Todos los metadatos son opcionales; `[]` vacío es válido.

### Reglas de validación — el checklist del parser

Cada casilla corresponde a una regla del Cap. VII.4 y a un mapa de prueba en
`maps/errors/`.

- [x] Primera línea no vacía: `nb_drones: <entero positivo>` → `missing_nb_drones.txt`
- [x] Exactamente un `start_hub:` → `no_start.txt`, `two_starts.txt`
- [x] Exactamente un `end_hub:`
- [x] Nombres de zona únicos → `duplicate_zone_name.txt`
- [x] Coordenadas enteras
- [x] Nombres sin guiones ni espacios → `dash_in_name.txt`
- [x] `connection:` solo referencia zonas **ya definidas antes** → `connection_unknown_zone.txt`
- [x] Sin conexiones duplicadas (`a-b` == `b-a`) → `duplicate_connection.txt`
- [x] `zone=` solo los cuatro valores válidos → `invalid_zone_type.txt`
- [x] `max_drones` / `max_link_capacity` enteros positivos → `negative_capacity.txt`
- [x] Metadatos sintácticamente válidos (todo par lleva `=`) → `malformed_metadata.txt`
- [x] `max_drones` en `start_hub`/`end_hub` se ignora **sin error** → `maps/valid/ignored_capacity.txt`
- [x] Líneas y colas de línea con `#` se ignoran
- [x] Cualquier otro fallo → excepción con **línea y causa**

⚠️ **No lo des por sentado — "definida antes en el archivo"**
El subject dice que las conexiones deben enlazar zonas *previamente definidas*.
Eso significa que el parser puede ser de **una sola pasada**: cuando llega a una
línea `connection:`, las dos zonas ya tienen que estar en el `Graph`. No
necesitas dos pasadas ni resolución diferida de referencias. Un mapa que declare
la conexión antes que la zona es un mapa **inválido**, no un mapa que debas
apañar.

⚠️ **No lo des por sentado — el guion es parte de la gramática**
Los nombres no pueden contener `-` precisamente porque `connection: a-b` usa el
guion como separador. Si permitieras `mid-zone` como nombre, `connection:
mid-zone-goal` sería ambiguo: ¿es `mid` con `zone-goal`, o `mid-zone` con
`goal`? No hay forma de desambiguarlo, y por eso el subject lo prohíbe de raíz.

### Comentarios: línea entera y cola de línea

Ambas formas son válidas y el parser actual soporta las dos:

```
# esta línea entera se ignora
hub: roof1 3 4 [zone=restricted]   # y esto también, desde la almohadilla
```

La implementación es la misma en los dos casos: cortar por el primer `#`,
aplicar `strip()`, y descartar la línea si queda vacía. Ver `clean_lines()` en
[`map_parser.py`](../fly_in/parsing/map_parser.py).

⚠️ **No lo des por sentado — conserva el número de línea original**
Al filtrar comentarios y líneas vacías, el índice dentro de tu lista limpia ya
no coincide con el número de línea del archivo. Si reportas el índice de la
lista, dirás "línea 4" cuando el usuario ve el error en la línea 9 de su fichero.
Por eso `clean_lines()` devuelve tuplas `(numero_original, texto)`: el número se
captura **antes** de filtrar.

---

## Parte 2 — La salida de la simulación

### Formato

- **Una línea por turno.**
- Movimientos separados por **un espacio**.
- Cada movimiento: `D<ID>-<destino>`, donde `<destino>` es:
  - el **nombre de una zona**, si el dron llega a una zona ese turno;
  - el **nombre de una conexión**, si el dron está en vuelo hacia una zona
    `restricted`.
- Los drones que **no se mueven** se omiten de la línea.
- Los drones que llegan a `end_hub` quedan entregados y no vuelven a aparecer.
- La simulación acaba cuando todos han llegado.

### Ejemplo del subject (Cap. VII.5)

```
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

### Nombre de la conexión en la salida

Una conexión no tiene nombre propio en el archivo de mapa: se identifica por sus
dos extremos. La convención de este proyecto, implementada en
[`Connection.name`](../fly_in/models/connection.py), es
`<zona_a>-<zona_b>` **en el orden en que apareció la línea `connection:` en el
archivo**, no en el orden en que el dron la recorre.

Ejemplo: con `connection: hub-roof1` y `roof1` marcada `restricted`, un dron que
va de `hub` a `roof1` produce:

```
D1-hub-roof1     # turno T: entra en la conexión, en tránsito
D1-roof1         # turno T+1: llega obligatoriamente a la zona
```

Y un dron que hiciera el camino inverso produciría también `D1-hub-roof1` en su
turno de tránsito, porque el identificador de la conexión es el mismo objeto.

⚠️ **No lo des por sentado — el tránsito ocupa dos líneas de salida**
Un movimiento hacia `restricted` cuesta 2 turnos y por tanto aparece en **dos
turnos consecutivos**: primero el nombre de la conexión, luego el de la zona. No
es un movimiento que se imprima una vez con coste 2; son dos líneas.

### Lo que el formato deja abierto

El subject no especifica estos puntos. Decide, documenta tu decisión en el
`README.md` y sé consistente:

| Punto abierto | Decisión de este proyecto |
|---|---|
| ¿Un turno sin ningún movimiento imprime línea vacía o no imprime nada? | **No imprime nada.** Un turno sin movimientos no aporta información y desalinearía el recuento de turnos visible |
| ¿En qué orden van los movimientos dentro de una línea? | **Por ID de dron ascendente.** Es determinista, reproducible entre ejecuciones y fácil de comparar en un test |
| ¿Se imprime algo al terminar (nº total de turnos, métricas)? | **Sí, pero en `stderr`**, para que `stdout` contenga exactamente el formato del subject y se pueda comparar automáticamente |

⚠️ **No lo des por sentado — separa `stdout` de `stderr`**
Si mezclas la salida de simulación con las métricas, los colores ANSI o los
mensajes de depuración en `stdout`, un evaluador no puede hacer
`make run > salida.txt` y comparar. Mantén `stdout` limpio: solo las líneas de
turno. Todo lo demás (visualización, métricas, avisos) va a `stderr`.
