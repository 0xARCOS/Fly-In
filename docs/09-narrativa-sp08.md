# SP08 contado de principio a fin

Continúa la historia de [`08-narrativa-sp06-sp07.md`](./08-narrativa-sp06-sp07.md).
Aquella terminaba con rutas **planificadas**: cada dron sabía qué haría en
cada instante de la ventana, y la tabla de reservas garantizaba que esos
planes no chocaban. Este documento cuenta cómo esos planes se convierten en
una **simulación**: quién mueve a los drones, cuándo se vuelve a planificar,
qué pasa con un dron en el aire y cómo se sabe que ningún turno ha roto una
regla. Como en la anterior, no es una guía de pasos (eso es
[`SP08-drone-y-simulador.md`](./build/SP08-drone-y-simulador.md)): explica
qué regla del subject obliga a que exista cada pieza y cómo se nota en la
ejecución.

> **Estado.** SP08 está implementado en
> [`fly_in/simulation/`](../fly_in/simulation/) (`drone.py`, `simulator.py`,
> `errors.py`) y cubierto por
> [`test/test_simulator.py`](../test/test_simulator.py). `main.py` ya ejecuta la
> simulación e imprime el número de turnos; la salida con el formato exacto del
> subject llega en [SP09](./build/SP09-formato-salida.md). Todas las trazas de
> este documento son salidas reales del programa, escritas con ese formato.

---

## 1. El problema: un plan no es una ejecución

Al acabar SP07, `WhcaPathfinder.plan()` devuelve para cada dron una lista de
`Step`: "espera en `start` hasta el instante 1, entra en `narrow` en el 2, llega
a `goal` en el 3". Es una promesa sobre el futuro, y le faltan tres cosas para
ser un programa que resuelve el mapa:

1. **Alguien que avance el reloj** y haga que los drones cumplan lo prometido,
   turno a turno, hasta que todos estén en `end_hub`.
2. **Alguien que renueve las promesas.** Las rutas solo cubren `W` turnos
   (la ventana de WHCA\*); un mapa que necesita 43 turnos exige volver a
   planificar varias veces por el camino.
3. **Alguien que desconfíe.** Si SP06 o SP07 tienen un bug, las rutas serán
   ilegales, y el subject no perdona: una sola zona con dos drones de más en un
   solo turno invalida la solución *(Cap. VII.2)*.

Esas tres responsabilidades son el `Simulator`. El `Drone` es solo el
recipiente del estado de cada agente.

---

## 2. El reloj, otra vez

La convención de tiempo no cambia: es la de la cabecera de
`reservation_table.py`, contada en la sección 2 de la narrativa anterior. El
**instante `t`** es la foto del mundo tras `t` turnos; el **turno `t`** lleva
del instante `t` al `t+1`, y es la línea `t+1` de la salida.

El simulador la hace concreta con un bucle: `turn` empieza en 0 y en cada
vuelta se ejecuta el turno `turn`. Un `Step` con `arrival_turn = 3` y
`cost = 1` se ejecuta en el turno 2 (sale del instante 2, llega al 3). Con
`cost = 2` sale en el turno 1 y ocupa dos turnos. Esa cuenta,
`salida = llegada - coste`, es la única que el simulador hace con los pasos, y
está en un solo sitio: `Drone.next_step(turn)`, que además **comprueba** que el
siguiente paso sale exactamente en `turn`. Si no, la ruta y el reloj se han
desincronizado y se lanza `SimulationError` en vez de ejecutar un paso en el
turno equivocado.

---

## 3. El dron

`Drone` guarda cinco cosas: su `id`, su `current_zone`, su `state`, su `path`
(los pasos que le quedan) y su `transit_connection`. Cumple el protocolo
`DroneLike` de SP07 sin heredar de nada, porque tiene `id` y `current_zone`, y
eso es todo lo que la búsqueda necesita.

`state` dice qué hizo el dron en el último turno:

| Estado | Significa | Aparece en la salida |
|---|---|---|
| `WAITING` | Se quedó en su zona | No (Cap. VII.5: los que no se mueven se omiten) |
| `MOVING` | Llegó a una zona adyacente | `D<id>-<zona>` |
| `IN_TRANSIT` | Entró en una conexión hacia una `restricted` y sigue en ella | `D<id>-<conexión>` |
| `ARRIVED` | Llegó a `end_hub` | Esa última vez; después nunca más |

El estado delicado es `IN_TRANSIT`. El subject dice que el dron que entra en una
conexión hacia una zona `restricted` *"MUST reach its destination during the
next turn. It can't wait extra turns on the connection"* *(Cap. VII.3)*. Un dron
en el aire no está en ninguna zona, así que no cuenta para ningún `max_drones`,
pero tampoco puede quedarse ahí. Hay dos maneras de representar "no está en
ninguna zona": poner `current_zone = None`, u **dejar `current_zone` en la zona
de la que salió** y marcar dónde está de verdad con `transit_connection`. Se
eligió la segunda. Con `None`, cada uso de `current_zone` en todo el programa
tendría que comprobar el caso vacío; así, la única pieza que tiene que saber
que un dron en el aire no ocupa su zona de origen es la que cuenta ocupación, y
la salida de SP09 tiene a mano el origen para nombrar la conexión.

---

## 4. Un turno por dentro

Cada vuelta del bucle de `Simulator.run()` hace cuatro cosas, siempre en este
orden:

```
mientras quede algún dron sin entregar:
    si turn >= max_turns: SimulationError nombrando a los atascados
    si toca: replanificar                         (4.1)
    decisiones ← FASE 1: decidir, sin tocar nada  (4.2)
    movimientos ← FASE 2: aplicarlas todas        (4.3)
    verificar el estado resultante                (4.4)
    traza.append(movimientos); turn += 1
```

### 4.1 Replanificar: cuándo y a quién

**Cuándo.** Al principio de cada media ventana (`turn % (W // 2) == 0`), y
también en cualquier turno en el que algún dron en tierra se haya quedado sin
ruta.

La media ventana es la cadencia clásica de WHCA\*. Si se replanificara cada
`W` turnos, justo cuando las rutas se agotan, los drones llegarían al final de
su plan sin margen: el último turno de la ventana lo planificó alguien que no
veía nada más allá. Replanificando a la mitad, siempre quedan `W/2` turnos de
cooperación por delante. Con `W = 1` la media ventana sería 0 y habría una
división por cero, así que la cadencia es `max(1, W // 2)`: como mínimo, cada
turno.

La segunda condición, la de la ruta agotada, parece un seguro que nunca se
usa: las rutas cubren `W` turnos y se renuevan cada `W/2`. Pero en el
challenger salta tres veces, siempre por el mismo motivo, y es la historia más
instructiva de este subproyecto. Está contada en la sección 6.4.

**A quién.** Solo a los drones en tierra. Primero se olvida el futuro:

```python
in_transit = {drone.id for drone in active if drone.in_transit}
self.table.clear_from(turn, keep=in_transit)
```

Es la llamada que SP06 diseñó exactamente para este momento. Todas las
reservas desde `turn` en adelante son predicciones que se van a rehacer, salvo
las de los drones en el aire: esos ya entraron en una conexión hacia una
`restricted`, su aterrizaje está comprometido y no pueden cambiar de idea. Si
`clear_from` borrara su reserva de aterrizaje, otro dron podría planificar
entrar en esa zona en ese instante, y el primero no tendría dónde llegar. Con
`keep`, sus reservas siguen en la tabla y los demás las esquivan.

Después se planifica a los que están en tierra con **una sola llamada**:

```python
paths = self.pathfinder.plan(grounded, turn)
```

Que sea `plan()` y no un bucle de `find_path()` no es un detalle. `plan()`
ordena a los drones, les pone la reserva provisional de SP07 (cada uno reserva
quedarse en su zona toda la ventana antes de que nadie planifique) y graba cada
ruta antes de buscar la siguiente. Si SP08 recorriera los drones llamando a
`find_path`, un dron que planifica antes podría reservar entrar en la zona de
otro que todavía no lo ha hecho, y dejarlo sin salida legal: la deuda técnica
que se resolvió al final de SP07.

Si aun así una ruta no cabe en la tabla (`ReservationError`), se convierte en
`SimulationError` con el turno en el mensaje. No debería pasar nunca; si pasa,
es un bug, y el mensaje dice dónde buscarlo.

### 4.2 Fase 1: decidir sin tocar nada

`_decide(turn, active)` recorre los drones activos y, para cada uno, apunta
qué va a hacer. **No modifica ningún dron.** Devuelve una lista de decisiones
`(dron, paso, movimiento)`:

- Un dron **en el aire** no decide: aterriza (`_land`). Su paso es el tránsito
  que empezó el turno anterior, y se comprueba que llega justo en `turn + 1`.
  No se le pregunta nada, porque preguntarle abriría la puerta a que "decidiera"
  esperar en el aire, que es exactamente lo que el subject prohíbe.
- Un dron **en tierra** toma su siguiente paso con `next_step(turn)`. Si es una
  espera, la decisión no lleva movimiento. Si es un movimiento, se construye un
  `Move` con `arrives = (coste == 1)`: hacia una zona normal o `priority` llega
  este mismo turno; hacia una `restricted`, este turno solo entra en la
  conexión.

¿Por qué separar decidir de aplicar? Por la regla *"Drones moving out of a zone
free up capacity for that same turn"* *(Cap. VII.3)*. Si el dron A sale de
`narrow` (capacidad 1) y el dron B entra en `narrow` en el mismo turno, el
movimiento de B es legal. Aplicando los movimientos según se recorre la lista,
el resultado dependería del orden: si B va antes que A, B vería `narrow`
ocupada. Con dos fases, todas las decisiones se toman contra el mismo estado
—el del instante `turn`— y el orden de la lista deja de importar.

En esta implementación hay una razón más profunda por la que el orden no
importa: el simulador **no decide nada por su cuenta**. Ejecuta las rutas que
SP07 ya validó contra la tabla, y en la tabla la regla de "las salidas liberan
sitio el mismo turno" ya está incorporada por la convención de tiempo (A está
en `(narrow, t)`, B llega a `(narrow, t+1)`). Las dos fases son la garantía de
que el simulador no rompe lo que la planificación hizo bien.

### 4.3 Fase 2: aplicar todo a la vez

`_apply(decisions)` recorre las decisiones y cambia el estado de cada dron:

| Decisión | Efecto |
|---|---|
| Espera | Consume el paso; `WAITING` |
| Entra en una conexión hacia una `restricted` (`arrives=False`) | `IN_TRANSIT`, `transit_connection` = la conexión. **No** consume el paso: el tránsito sigue pendiente |
| Llega (`arrives=True`) | Consume el paso, `current_zone` = destino, sale de la conexión; `ARRIVED` si es `end_hub`, si no `MOVING` |

Devuelve los movimientos del turno ordenados por id de dron, que es el orden
en que SP09 los imprimirá. Las esperas no generan `Move`: el subject dice que
los drones que no se mueven se omiten de la línea.

### 4.4 Verificar: desconfiar de SP06 y SP07

Tras aplicar, `_verify` **recuenta** la ocupación sin mirar la tabla de
reservas: cuántos drones hay en cada zona (sin contar los que están en el aire
ni los entregados) y cuántos movimientos usan cada conexión este turno. Si
alguna cifra supera `max_drones` o `max_link_capacity`, lanza
`SimulationError` con el turno y la zona o conexión.

Si SP06 y SP07 funcionan, esta comprobación nunca salta. Existe para el día en
que no funcionen: un bug de capacidad descubierto aquí aparece como "turno 7:
2 drones en `narrow`", en lugar de como una solución que el evaluador rechaza
sin decir por qué. Es la segunda mitad de la recomendación de la guía: **la
fase 1 confía en la tabla y la fase 2 lo verifica**, con una lógica distinta y
mucho más simple (contar), para que un error en la lógica complicada no pase
desapercibido.

### 4.5 Los dos finales malos

Una simulación puede fallar de dos maneras, y las dos tienen que terminar en un
mensaje, nunca en un cuelgue: el subject cuenta como no funcional un programa
que se cuelga *(Cap. III.1)*.

**El mapa es imposible.** Si `end_hub` no es alcanzable desde `start_hub`, se
sabe antes de empezar: `AbstractDistance` no tiene distancia para `start_hub`.
El constructor del `Simulator` lanza `SimulationError` en el turno 0. (`main.py`
ya lo comprobaba desde SP03; el simulador lo repite para no depender de quién
lo llame.)

**La simulación no converge.** WHCA\* no es completo: hay configuraciones en
las que los drones se ceden el paso indefinidamente. Contra eso está el límite
de seguridad:

```python
max_turns = nb_drones * len(graph.zones) * MAX_TURNS_FACTOR   # factor 4
```

El razonamiento: un dron solo tarda como mucho 2 turnos por zona (si todas
fueran `restricted`), y si los drones fueran en fila india, uno detrás de otro,
serían `nb_drones` veces eso. El factor 4 deja el doble de margen sobre ese
peor caso razonable. En el challenger el límite es 25 × 54 × 4 = 5400 turnos,
frente a los 43 que tarda de verdad: holgado, pero finito.

Al alcanzarlo, el mensaje nombra a cada dron sin entregar y dónde está:

```
Simulation did not converge after 2 turns. Undelivered drones: D2 (at narrow), D3 (at start)
```

(Ese mensaje sale de un test que fuerza `max_turns = 2` en `bottleneck.txt`.)
Con esto se puede depurar; con un cuelgue, no.

---

## 5. Lo que sale: la traza

`run()` devuelve la **traza**: una lista con un elemento por turno, y en cada
uno la lista de `Move` de ese turno. Su longitud es el número de turnos, que es
la nota *(Cap. VII.6)*.

Un `Move` lleva el dron, el origen, el destino, la conexión y `arrives`. Con
eso SP09 no necesita deducir nada: si `arrives`, imprime `D<id>-<destino>`; si
no, `D<id>-<conexión>`. Un tránsito hacia una `restricted` genera **dos** `Move`
en dos turnos consecutivos, el primero con `arrives=False` y el segundo con
`arrives=True`, que es justo lo que el subject pide ver en la salida: dos líneas,
una con la conexión y otra con la zona.

El simulador no formatea texto. Separarlo tiene la misma razón que tuvo separar
`Step` de la lista de zonas en SP07: el que ya sabe la información la entrega
estructurada, y el que la presenta no tiene que reconstruirla.

---

## 6. Todo junto: cómo se ve en la ejecución

Las trazas siguientes están en el formato del subject, una línea por turno.
Son salidas reales de `Simulator.run()`.

### 6.1 `bottleneck.txt`: el reloj y las dos fases

Tres drones, `start → narrow → goal`, `narrow` y sus dos conexiones con
capacidad 1:

```
D1-narrow
D1-goal D2-narrow
D2-goal D3-narrow
D3-goal
```

En el turno 2, D1 sale de `narrow` y D2 entra, en el mismo turno. Es la regla
de "las salidas liberan sitio" funcionando sin una línea específica para ella:
D1 está en `(narrow, 1)` y D2 llega a `(narrow, 2)`. Cuatro turnos es el
mínimo: `narrow` solo admite un dron por instante y cada uno necesita dos
turnos para cruzar.

El test `test_result_does_not_depend_on_drone_list_order` ejecuta este mapa
(y los otros 18) con la lista de drones invertida y comprueba que la traza es
**idéntica**, carácter a carácter.

### 6.2 `restricted_chain.txt` con `W = 2`: replanificar con drones en el aire

`start → r1 → r2 → goal`, con `r1` y `r2` `restricted`. Con tres drones y
`W = 2`, la cadencia es 1: **se replanifica en cada turno**, lo que obliga a
que `keep` funcione continuamente.

```
D1-start-r1
D1-r1
D1-r1-r2 D2-start-r1
D1-r2 D2-r1
D1-goal D2-r1-r2 D3-start-r1
D2-r2 D3-r1
D2-goal D3-r1-r2
D3-r2
D3-goal
```

Lo que pasa por dentro, replanificación a replanificación:

| Turno | En el aire (`keep`) | Qué se replanifica |
|---|---|---|
| 0 | — | D1 sale hacia `r1`; D2 y D3 esperan en `start` |
| 1 | D1 | D2 y D3. D1 no se toca: aterriza en `r1` en el 2 pase lo que pase |
| 2 | — | D1 sigue a `r2`; D2 sale hacia `r1` (la conexión `start-r1` ya está libre) |
| 3 | D1, D2 | Solo D3, que espera un turno más: D2 ocupa `start-r1` (capacidad 1) también en su segundo turno de tránsito |

Sin `keep`, en el turno 1 `clear_from(1)` borraría las reservas de D1 desde el
instante 1: su segundo turno en `start-r1` y su aterrizaje en `r1`. La tabla
diría que la conexión está libre, D2 planificaría entrar en ella en ese mismo
turno, y habría dos drones en una conexión de capacidad 1. Es el tipo de bug
que no aparece con un dron y que depende de que la replanificación caiga justo
con alguien en el aire; con `W = 2` cae siempre. Por eso el test de invariantes
se ejecuta con `W` = 1, 2, 3 y 8. Con `keep` desactivado a propósito, la
verificación de la sección 4.4 lo detiene en el acto:

```
Turn 2: 2 drones on 'start-r1' (max_link_capacity=1)
```

("Turn 2" es la línea 2 de la salida, es decir, el turno 1 del bucle.)

### 6.3 `medium/02_circular_loop.txt`: 15 turnos, y por qué es el óptimo

Seis drones. Un anillo de cuatro zonas de capacidad 2 (`loop_a` … `loop_d`), y
una única salida: `loop_b → exit_point → goal`, donde `exit_point` es
`restricted` y la conexión `loop_b-exit_point` tiene capacidad 1.

```
D1-loop_a D2-loop_a
D1-loop_b D2-loop_b D3-loop_a D4-loop_a
D1-loop_b-exit_point D3-loop_b D5-loop_a
D1-exit_point
D1-goal D2-loop_b-exit_point D4-loop_b D6-loop_a
D2-exit_point
D2-goal D3-loop_b-exit_point D5-loop_b
D3-exit_point
D3-goal D4-loop_b-exit_point D6-loop_b
D4-exit_point
D4-goal D5-loop_b-exit_point
D5-exit_point
D5-goal D6-loop_b-exit_point
D6-exit_point
D6-goal
```

El cuello de botella es la conexión `loop_b-exit_point`: con la lectura
estricta de SP06, un dron que va hacia una `restricted` **ocupa la conexión los
dos turnos del tránsito**, así que con capacidad 1 solo entra un dron cada dos
turnos. El primero puede entrar en el turno 3 (dos turnos para llegar a
`loop_b`); el sexto, cinco entradas después, en el 13; aterriza en
`exit_point` en el 14 y llega a `goal` en el 15. Ninguna planificación puede
hacerlo mejor con esa regla. El subject pide ≤ 15: se cumple justo.

La referencia de Mario da 10 turnos porque usa la lectura permisiva (la
conexión solo cuenta el turno en que se entra). Es una diferencia de
**interpretación del subject**, decidida y documentada en SP06, no de calidad
de la búsqueda.

Fíjate también en lo que **no** pasa: nadie entra en `loop_c` ni en `loop_d`.
Dar la vuelta al anillo no acerca a nadie a la salida, y la heurística de SP05
lo sabe; los drones esperan en `loop_a` y `loop_b`, que tienen sitio para dos.

### 6.4 El challenger: la regla que parecía un seguro

En el challenger hay una cadena de zonas `restricted`
(`conv_restricted7 → 8 → 9`). Un dron que la recorre pasa dos turnos en el aire
por cada zona, y con `W = 8` la replanificación es cada 4 turnos. Resultado: hay
drones que están **en el aire en todos los turnos de replanificación**. Nunca
se replanifican por cadencia (están en `keep`), y siguen ejecutando la ruta que
recibieron la última vez que estaban en tierra.

Esa ruta vieja cubría `W` turnos desde entonces, y se acaba justo cuando el
dron aterriza. En el turno 13, D2 aterriza en `conv_restricted9` y D4 en
`conv_restricted8`, y los dos se quedan sin pasos. Lo mismo ocurre en los
turnos 21 y 29, con otros drones.

Sin la regla de "ruta agotada", en el turno 13 la fase 1 encontraría dos drones
en tierra sin nada que hacer. Había dos respuestas posibles:

- **Que esperen en el sitio.** Parece inofensivo, pero su espera no está en la
  tabla: otro dron podría haber planificado entrar en `conv_restricted9` en ese
  instante. Sería una colisión fabricada por el propio simulador.
- **Replanificar en ese mismo turno.** Es lo que se hace. `clear_from(13)` y
  `plan()` para todos los que están en tierra; si esos drones tienen que
  esperar, la espera queda reservada como cualquier otra.

Con `W` = 2 o 3 no ocurre nunca en ningún mapa; con `W = 8`, exactamente esas
tres veces. Es el caso típico de una regla que "no hace falta" hasta que el mapa
difícil la necesita.

---

## 7. Cómo sabemos que funciona

El test más valioso del proyecto no prueba el simulador: prueba **la traza**.
`assert_simulation_is_legal`, en `test/test_simulator.py`, recorre la traza
como lo haría un evaluador externo: solo conoce el grafo y las reglas del Cap.
VII. **No usa `ReservationTable` ni nada del simulador**; si los usara, solo
comprobaría que el código es coherente consigo mismo. Lleva su propia cuenta de
dónde está cada dron y comprueba, turno a turno:

- que ninguna zona supera `max_drones` y ninguna conexión `max_link_capacity`;
- que cada movimiento sale de donde el dron estaba y va por una conexión real,
  nunca hacia una `blocked`;
- que un tránsito hacia una `restricted` dura exactamente dos turnos, sin
  cambiar de rumbo, y que ir a una zona normal dura uno;
- que ningún dron aparece dos veces en un turno ni se cruza de frente con otro;
- que los entregados no vuelven a moverse y que al final lo están todos.

Se ejecuta sobre los 9 mapas válidos con `W` = 1, 2, 3 y 8, y sobre los 10
oficiales con `W` = 2 y 8.

Para comprobar que los tests cazan fallos de verdad, se introdujeron bugs a
propósito en el simulador, uno a uno:

| Bug introducido | ¿Lo caza algún test? |
|---|---|
| `clear_from` sin `keep` (se olvidan las reservas de los drones en el aire) | Sí |
| Replanificar también a los drones en el aire | Sí |
| El tránsito a `restricted` en un solo turno | Sí |
| Quitar la replanificación por ruta agotada | Sí (el challenger se queda sin plan en el turno 13) |
| Replanificar cada `W` en vez de cada `W/2` | Al principio, **no**: la regla de ruta agotada lo compensaba y las trazas seguían siendo legales. Se añadió `test_replans_every_half_window` |

Y `test_official_benchmarks` fija los turnos actuales de los diez mapas
oficiales: si una mejora futura los cambia, el test lo dice, y el cambio tiene
que ser a propósito.

---

## 8. Lo que este diseño no garantiza

- **Optimalidad.** WHCA\* es voraz entre drones: el que planifica primero se
  queda con las mejores reservas. Los resultados coinciden con la referencia en
  8 de los 10 mapas oficiales, pero no hay garantía de óptimo en general.
- **Convergencia.** Sigue sin ser completo; el límite de seguridad convierte un
  bucle infinito en un error claro, no en una solución.
- **Que el orden de planificación dé igual.** El orden de la *lista* de drones
  no importa (sección 6.1), pero el *criterio* de prioridad sí. Medido en los
  mapas oficiales: por id y `nearest_first` empatan siempre; `farthest_first`
  casi triplica los turnos del challenger (124 frente a 43) por el coste de la
  reserva provisional de SP07, y `rotating` también empeora (74). Por eso el
  valor por defecto es por id.
- **Que `W` importe.** Con `W` = 4, 8 y 12 los turnos son idénticos en los 19
  mapas. `W` afecta al tiempo de cálculo (el challenger tarda 0,24 s con `W = 4`
  y 0,64 s con `W = 12`) y a cuándo salta la replanificación por ruta agotada,
  pero no, hoy, a la nota. El ajuste fino es de SP11.

---

## 9. Resumen: quién hace qué

| Pieza | Responsabilidad | Regla del subject |
|---|---|---|
| `Drone` | Guarda posición, estado, ruta pendiente y conexión en tránsito; `next_step` comprueba que la ruta y el reloj van sincronizados | Cap. VII.3 (estados de movimiento) |
| `Simulator.__init__` | Crea los drones en `start_hub`; detecta el mapa imposible en el turno 0; calcula el límite de seguridad | Cap. III.1 (no colgarse) |
| `_must_replan` / `_replan` | Cada `W/2` turnos o si a alguien se le agotó la ruta: `clear_from(turn, keep=en el aire)` y `plan()` para los que están en tierra | Cap. VII.3 (no se espera en el aire) |
| `_decide` | Fase 1: qué hace cada dron, sin tocar nada; los que están en el aire aterrizan sin elección | Cap. VII.3 (las salidas liberan sitio el mismo turno) |
| `_apply` | Fase 2: aplica todo a la vez y devuelve los `Move` del turno | Cap. VII.5 (los que no se mueven se omiten) |
| `_verify` | Recuenta ocupación sin la tabla; `SimulationError` en el turno exacto si algo no cuadra | Cap. VII.2 (capacidades) |
| `run` | El bucle; devuelve la traza, cuya longitud es el número de turnos | Cap. VII.6 (la métrica) |
| `Move` | Lo que necesita SP09 para imprimir `D<id>-<zona>` o `D<id>-<conexión>` | Cap. VII.5 (formato) |
