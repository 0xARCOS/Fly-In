# El problema — reglas normativas del subject

Este documento traduce el PDF del subject ([`Fly-In.pdf`](./Fly-In.pdf)) a una
lista de reglas ordenadas y sin ambigüedad. **Es la fuente normativa de la
guía**: cuando un subproyecto dice "según la regla de ocupación", se refiere a
una de estas. Ante cualquier contradicción, manda el PDF.

Cada regla lleva la referencia al capítulo del subject de donde sale, para que
puedas verificarla tú mismo en treinta segundos.

---

## 1. El objetivo, en una frase

> Mover **todos** los drones desde la zona `start_hub` hasta la zona `end_hub`
> en el **menor número de turnos de simulación posible**, respetando todas las
> reglas de ocupación y movimiento. *(Cap. VII)*

El número de turnos es literalmente tu nota de rendimiento. Menos turnos =
mejor. *(Cap. VII.6)*

## 2. Restricciones del proyecto *(Cap. V)*

| Restricción | Detalle |
|---|---|
| **Python ≥ 3.10** | Puedes usar `match`, `X \| None`, `dict[str, int]` sin `typing` |
| **Sin librerías de grafos** | `networkx`, `graphlib`, etc. están **prohibidas**. El grafo lo escribes tú |
| **Type-safe** | `flake8` y `mypy` son obligatorios y deben pasar sin errores |
| **Completamente orientado a objetos** | Y tendrás que demostrarlo en la peer-review |
| **Sin crashes** | Una excepción no capturada durante la evaluación = proyecto no funcional *(Cap. III.1)* |

⚠️ **No lo des por sentado — "completamente orientado a objetos"**
No significa "meter todo dentro de clases". Significa que el dominio está
modelado con objetos que tienen responsabilidades claras: una `Zone` sabe su
coste de entrada, una `Connection` sabe quién está al otro extremo, un
`Simulator` sabe avanzar un turno. Funciones auxiliares privadas a nivel de
módulo (como las del parser actual) son perfectamente defendibles; lo que no
lo es es un `main.py` de 400 líneas con diccionarios sueltos.

## 3. El grafo *(Cap. VI)*

- El mapa es una **red de zonas conectadas**. Las zonas son nodos, las
  conexiones son aristas **bidireccionales**.
- Hay **exactamente una** zona `start_hub` y **exactamente una** `end_hub`.
- Las coordenadas `x`/`y` **siempre son enteras**. Sirven para dibujar y, si
  quieres, para una heurística geométrica — pero **no definen adyacencia**: dos
  zonas solo son vecinas si existe una línea `connection:` entre ellas.

⚠️ **No lo des por sentado — las coordenadas no son una cuadrícula**
Esto no es un mapa de casillas. Dos zonas en `(0,0)` y `(1,0)` no están
conectadas por estar pegadas; lo están si y solo si hay `connection: a-b`. La
distancia euclídea entre coordenadas es una heurística *posible*, pero mala: la
buena es la distancia real por el grafo (ver [`SP05`](./build/SP05-heuristica-abstracta.md)).

## 4. Tipos de zona y coste de movimiento *(Cap. VI, VII.3)*

El coste de un movimiento lo fija **el tipo de la zona de destino**, nunca el
de la zona de origen ni el de la conexión.

| `zone=` | Coste de entrada | Entrable | Notas |
|---|---|---|---|
| `normal` | 1 turno | sí | Valor por defecto |
| `priority` | 1 turno | sí | Mismo coste que `normal`, pero **debe preferirse** en el pathfinding |
| `restricted` | 2 turnos | sí | El dron ocupa la **conexión** durante el tránsito |
| `blocked` | — | **no** | Inaccesible. Cualquier ruta que la use es inválida |

⚠️ **No lo des por sentado — `priority` no es más barata**
Cuesta 1, igual que `normal`. La preferencia solo se aplica **en los empates**:
entre dos rutas de coste total idéntico, eliges la que pasa por más zonas
`priority`. Si la implementas como "coste 0.5" rompes la admisibilidad de la
heurística y obtendrás rutas raras.

## 5. Reglas de ocupación de zona *(Cap. VII.2)*

1. Por defecto una zona admite **como máximo un dron** en un turno dado.
2. `max_drones=N` en los metadatos sube ese límite a N.
3. **Excepciones — `start_hub` y `end_hub` no tienen límite de capacidad:**
   - todos los drones empiezan en `start_hub` y pueden compartirla;
   - cualquier número de drones puede llegar a `end_hub`, y ahí se consideran
     *entregados*.
4. Dos drones no pueden entrar en la misma zona el mismo turno si la capacidad
   no lo permite.
5. `max_link_capacity=N` en una conexión limita cuántos drones la atraviesan
   simultáneamente (por defecto 1).
6. Los drones **pueden moverse a la vez**, siempre que se respeten todas las
   capacidades.

⚠️ **No lo des por sentado — nunca reserves `start_hub`/`end_hub`**
Es el error que más tiempo cuesta diagnosticar. Si tu tabla de reservas trata
`start_hub` como una zona normal de capacidad 1, con 5 drones el cuarto no podrá
ni salir de casa, y el síntoma que verás es "mi algoritmo no encuentra ruta"
—cuando el problema no está en la búsqueda.

## 6. Mecánica del turno *(Cap. VII.3)*

En cada turno, cada dron puede hacer **una** de estas tres cosas:

1. Moverse a una zona adyacente conectada, si la capacidad lo permite.
2. Entrar en una **conexión hacia una zona `restricted`** (movimiento de 2
   turnos). En ese caso **debe** llegar a su destino el turno siguiente:
   no puede esperar en la conexión.
3. Quedarse quieto (esperar deliberadamente, o porque está bloqueado).

Y dos reglas de resolución que determinan cómo escribes el bucle:

- **Un dron que sale de una zona libera su capacidad en ese mismo turno.** Un
  segundo dron puede entrar en la zona que el primero acaba de dejar, en el
  mismo turno.
- Una zona debe tener capacidad disponible para admitir un dron **después de
  contar todas las salidas de ese turno**.

⚠️ **No lo des por sentado — por qué esto obliga a dos fases**
Si aplicas los movimientos uno a uno recorriendo la lista de drones, el
resultado depende del orden de la lista: el dron que se procesa primero ve un
estado distinto del que ve el último. La regla de "las salidas liberan espacio
en el mismo turno" solo es implementable de forma determinista si separas
**decidir** (calcular todos los destinos contra el estado del turno T) de
**aplicar** (mover todos a la vez). Ver [`SP08`](./build/SP08-drone-y-simulador.md).

⚠️ **No lo des por sentado — el tránsito `restricted` no ocupa zona**
Un dron que entra en la conexión hacia una `restricted` en el turno T:
- ocupa **la conexión** en T y en T+1,
- ocupa **la zona destino** a partir de T+2,
- en T+1 no ocupa ninguna zona: está literalmente en el aire.

## 7. Restricciones del parser *(Cap. VII.4)*

El archivo de entrada debe respetar exactamente:

- La primera línea define `nb_drones: <entero positivo>`.
- El programa debe soportar **cualquier** número de drones.
- Exactamente un `start_hub:` y un `end_hub:`.
- Nombres de zona **únicos** y coordenadas enteras válidas.
- Los nombres admiten cualquier carácter **excepto guiones y espacios** (el
  guion es el separador de la sintaxis `connection:`).
- Las conexiones solo enlazan zonas **ya definidas antes** en el archivo.
- La misma conexión no puede aparecer dos veces (`a-b` y `b-a` son la misma).
- Los bloques de metadatos deben ser sintácticamente válidos.
- `zone=` solo admite `normal`, `blocked`, `restricted`, `priority`. Cualquier
  otro valor es un error de parseo.
- `max_drones` y `max_link_capacity` deben ser **enteros positivos**.
- `max_drones` **se ignora** en `start_hub` y `end_hub` — está permitido que
  aparezca y **no es un error de validación**.
- Cualquier otro fallo de formato debe **parar el programa** y devolver un
  mensaje claro **indicando la línea y la causa**.
- Los comentarios empiezan por `#` y se ignoran.

⚠️ **No lo des por sentado — "ignorado" no es "validado"**
`start_hub: base 0 0 [max_drones=-1]` **debe parsear sin error**, porque en
`start_hub` ese metadato se ignora por completo. Si lo validas antes de
comprobar el rol de la zona, rechazarás un mapa legal. Es una divergencia real
del parser actual, anotada en [`SP02`](./build/SP02-parser.md#deuda-conocida).

## 8. Formato de salida *(Cap. VII.5)*

- Una **línea por turno** de simulación.
- Cada línea lista todos los movimientos de ese turno, **separados por
  espacios**, en el formato `D<ID>-<zona>` o `D<ID>-<conexión>` para drones aún
  en vuelo hacia una zona `restricted`.
- Los drones que **no se mueven** en un turno se **omiten** de esa línea.
- Los drones que llegan a `end_hub` se consideran entregados y **dejan de
  rastrearse**.
- La simulación termina cuando **todos** los drones han llegado.

Ejemplo literal del subject:

```
D1-roof1 D2-corridorA
D1-roof2 D2-tunnelB
D1-goal D2-goal
```

## 9. Representación visual — es obligatoria *(Cap. VII.1)*

El subject la lista dentro de la parte mandatory, no como bonus:

> *Your implementation must provide visual feedback of the simulation, either
> through: colored terminal output / a graphical interface / both.*

Mínimo aceptable: salida de terminal a color mostrando movimientos de drones y
estado de las zonas. Los `color=` del mapa existen precisamente para esto.
Ver [`SP10`](./build/SP10-visualizacion.md).

## 10. Benchmarks de rendimiento *(Cap. VII.7)*

| Categoría | Mapa de referencia | Drones | Objetivo |
|---|---|---|---|
| Fácil | Linear path | 2 | ≤ 6 turnos |
| Fácil | Simple fork | 4 | ≤ 8 turnos |
| Fácil | Basic capacity | 4 | ≤ 6 turnos |
| Media | Dead end trap | 5 | ≤ 12 turnos |
| Media | Circular loop | 6 | ≤ 15 turnos |
| Media | Priority puzzle | 5 | ≤ 12 turnos |
| Difícil | Maze nightmare | 8 | ≤ 30 turnos |
| Difícil | Capacity hell | 12 | ≤ 35 turnos |
| Difícil | Ultimate challenge | 15 | ≤ 45 turnos |
| Challenger *(opcional, no puntúa)* | The Impossible Dream | 25 | batir 45 turnos |

Genéricamente: fácil < 10 turnos, media 10–30, difícil < 60.

> ℹ️ **Los mapas de evaluación pueden ser distintos de los del subject**
> *(Cap. X)*. No ajustes tu algoritmo a un mapa concreto: ajústalo a la clase de
> topología.

## 11. Qué se entrega *(Cap. VIII, X)*

Una simulación funcional en Python con:

- parser del formato de entrada,
- motor de simulación que respeta movimiento y ocupación,
- algoritmo(s) de pathfinding que minimicen turnos,
- sistema de representación visual,
- salida en el formato especificado,

más un `README.md` **en inglés**, en la raíz del repositorio, cuya primera línea
sea, en cursiva:

```
*This project has been created as part of the 42 curriculum by <login>.*
```

y que contenga al menos: **Description**, **Instructions**, **Resources** (con
mención explícita de cómo se usó la IA y en qué partes), descripción detallada
de las decisiones de algoritmo y estrategia de implementación, documentación de
la representación visual, y un ejemplo de entrada con su salida esperada.

⚠️ **No lo des por sentado — los tests no se entregan**
*Cap. III.3* dice literalmente: *"Create test programs to verify project
functionality **(not submitted or graded)**"*. Los tests de esta guía existen
porque son la única forma de saber si tu código funciona antes de la review, no
porque el subject los exija para aprobar. Eso sí: en la evaluación pueden
pedirte **escribir o modificar código en vivo** *(Cap. X)*, y una suite de tests
es lo que hace que ese cambio sea seguro.
