# SP11 contado de principio a fin

Continúa [`11-narrativa-sp10.md`](./11-narrativa-sp10.md) y cierra la serie. El
programa ya resuelve los mapas, los escribe en el formato exacto y se ve. Este
último tramo no añade funcionalidad: **mide**, **decide con datos** y
**entrega**. Es el que convierte "funciona en mi máquina" en "cualquiera lo
clona, lo ejecuta y comprueba que cumple".

> **Estado.** Métricas en
> [`fly_in/simulation/metrics.py`](../fly_in/simulation/metrics.py), runner en
> [`fly_in/benchmarks.py`](../fly_in/benchmarks.py) (`make bench`), tests en
> [`test/test_metrics.py`](../test/test_metrics.py) y el
> [`README.md`](../README.md) final. La guía de pasos es
> [`SP11-benchmarks-y-readme.md`](./build/SP11-benchmarks-y-readme.md).

---

## 1. El problema: medir de forma repetible

El subject da una tabla de objetivos por mapa *(Cap. VII.7)*, pregunta por
eficiencia y no solo por turnos *(Cap. VII.1)*, y avisa de que **los mapas de
evaluación pueden ser otros** *(Cap. X)*. De ahí salen tres necesidades:

- una medición que se pueda repetir con un solo comando, porque se va a
  ejecutar muchas veces;
- métricas que expliquen *dónde* se ganan o se pierden turnos, no solo
  cuántos salen;
- ajustar solo **parámetros globales** (la ventana `W` y el criterio de
  prioridad), nunca un truco para un mapa concreto.

---

## 2. Las métricas: leídas de la traza

`Metrics.from_trace(trace, nb_drones)` calcula todo a partir de la **traza**,
no del estado interno del simulador: son las mismas cifras que obtendría
alguien que solo leyera la salida.

| Métrica | Cómo se calcula | Qué dice |
|---|---|---|
| `turns` | Turnos con algún movimiento | La nota |
| `total_moves` | Número total de `Move` (un tránsito cuenta 2) | Coste total de ruta: turnos-dron en marcha |
| `total_waits` | Σ turno de entrega − `total_moves` | Turnos-dron parados: la cola |
| `avg_moves_per_turn` | `total_moves / turns` | Paralelismo: cuántos drones avanzan a la vez |
| `avg_turns_per_drone` | Media del turno de entrega | Cuánto tarda el dron típico, no solo el último |
| `peak_airborne` | Máximo de `Move` con `arrives=False` en un turno | Uso de las zonas `restricted` |
| `seconds` | Tiempo de cálculo, sin la animación | Eficiencia |

Salen por `stderr` con `--metrics`, en la tarjeta final de la ventana y en
`make bench`. En `bottleneck.txt` se comprueban a mano en un test: D1 entrega
en el turno 2, D2 en el 3 y D3 en el 4, así que el turno medio es 3; cada uno se
mueve dos turnos, así que hay 6 movimientos y (2 + 3 + 4) − 6 = 3 esperas.

---

## 3. `make bench`

El runner imprime dos tablas. La primera, los diez mapas oficiales con la
configuración por defecto:

```
map                                  drones turns  target  ok     time moves/t avg.dlv waits
--------------------------------------------------------------------------------------------
easy/01_linear_path.txt                   2     4     ≤ 6  ✅      0ms    1.50     3.5     1
easy/02_simple_fork.txt                   4     4     ≤ 8  ✅      1ms    3.00     3.5     2
easy/03_basic_capacity.txt                4     4     ≤ 6  ✅      0ms    3.00     3.5     2
medium/01_dead_end_trap.txt               5     8    ≤ 12  ✅      1ms    2.50     6.0    10
medium/02_circular_loop.txt               6    15    ≤ 15  ✅      6ms    2.00    10.0    30
medium/03_priority_puzzle.txt             5     7    ≤ 12  ✅      1ms    3.00     5.4     6
hard/01_maze_nightmare.txt                8    13    ≤ 30  ✅     10ms    4.38     9.5    19
hard/02_capacity_hell.txt                12    16    ≤ 35  ✅     23ms    6.19    10.5    27
hard/03_ultimate_challenge.txt           15    26    ≤ 45  ✅     76ms    7.46    19.0    91
challenger/01_the_impossible_dream.txt   25    43    < 45  ✅    247ms   11.05    31.0   300
```

Los diez cumplen. Los objetivos viven en `BENCHMARKS`, una tupla de
`Benchmark(categoría, ruta, drones, máximo, etiqueta)`. El challenger pide
*batir* 45, así que su máximo es 44. Un test comprueba que cada fichero existe y
tiene el número de drones que dice la tabla, y otro, que la configuración por
defecto cumple los diez objetivos: si una mejora futura rompe uno, el test lo
dice.

La misma tabla alimenta el **PAR** de la visualización: `BenchmarkSuite.target_for(ruta)`
reconoce los mapas oficiales por su nombre de fichero.

La segunda tabla ejecuta los diez mapas con **12 configuraciones**: `W` = 4, 8
y 16 por cada uno de los cuatro criterios de prioridad. Resumida en turnos
totales:

| | id | nearest | farthest | rotating |
|---|---|---|---|---|
| W = 4 | **140** | **140** | 230 | 170 |
| W = 8 | **140** | **140** | 266 | 177 |
| W = 16 | **140** | **140** | 276 | 207 |

---

## 4. Decidir con datos

**El criterio de prioridad.** `id` y `nearest_first` empatan en los diez
mapas; los otros dos pierden, y el motivo está en SP07. Antes de planificar, cada
dron reserva quedarse donde está durante toda la ventana (la reserva
provisional). Con `farthest_first` planifica primero el que va **detrás**, que
ve al de delante "quieto" y espera, aunque el de delante fuera a irse. Cuanto
más larga es la ventana, más dura esa espera ficticia: por eso `farthest`
empeora con `W` (230 → 266 → 276). `rotating` rompe la fila india que forman
los drones al salir de `start_hub`. Se eligió **`id`**: empata con el mejor y
es el más fácil de explicar.

**La ventana.** Con los buenos criterios, `W` no cambia ni un turno entre 4 y
16. Se mantiene **8**: deja margen para topologías más retorcidas que las
oficiales (Cap. X) a un coste despreciable: los diez mapas juntos tardan
0,21 s con `W = 4` y 0,30 s con `W = 16`.

**Lo que no se tocó.** Ni la heurística ni ninguna regla se ajustaron a un mapa
concreto. Si hubiera hecho falta, la guía pedía antes *mirar dónde se pierden
los turnos*, y eso es lo que cuenta la sección siguiente.

---

## 5. Dónde están los turnos que "faltan"

El proyecto de referencia de Mario da 10 en medium/02 y 6 en medium/03, frente
a nuestros 15 y 7. Antes de tocar nada, se midió por qué.

**medium/02.** La única salida es `loop_b → exit_point`, con `exit_point`
`restricted` y la conexión de capacidad 1. Con la lectura **estricta** de SP06
(el dron ocupa la conexión los dos turnos del tránsito), entra un dron cada dos
turnos: el primero en el turno 3 y el sexto en el 13, que aterriza en el 14 y
entrega en el 15. Es el óptimo.

**medium/03.** La ruta rápida pasa por `fast_path` (capacidad 1): entrega
como mucho un dron por turno, en los turnos 4, 5 y 6. La lenta pasa por
`slow_path1`, `restricted`: con la lectura estricta, el segundo dron que la usa
no puede entrar en la conexión hasta que el primero la deja libre, y entrega en
el turno 7. Hasta el turno 6 solo caben 4 entregas; el quinto dron necesita el 7.
También es el óptimo.

**La prueba.** Se ejecutó este mismo algoritmo con la lectura **permisiva**
(la conexión solo cuenta el turno de salida), cambiando únicamente
`can_move` y `reserve_move` de la tabla. Resultado: **10 y 6**, exactamente
los de Mario. La diferencia es la regla, no la búsqueda; en los otros ocho
mapas los resultados son idénticos. La lectura estricta se mantiene porque es
la literal (*"the drone occupies the connection during transit"*), y el
`README.md` lo explica.

---

## 6. El `README.md`

Va en inglés y en la raíz *(Cap. VIII)*, y su **primera línea** es literal y en
cursiva: `*This project has been created as part of the 42 curriculum by
ariarcos.*`. El login se tomó del usuario del sistema; hay que confirmarlo
antes de entregar.

Contiene las secciones obligatorias (**Description**, **Instructions**,
**Resources** con el uso de la IA especificado por tareas y partes,
**Algorithm and implementation strategy**, **Visual representation**,
**Example** con entrada y salida esperada) y lo que la guía recomendaba añadir:
la tabla de benchmarks con resultados reales, la comparación de
configuraciones, las limitaciones conocidas, la complejidad de cada pieza y
capturas de la ventana pygame.

Cada afirmación del README se comprobó ejecutándola. Así apareció el último
bug del proyecto: el README promete que `make run MAP=… > out.txt` deja solo
las líneas de turno y que `wc -l` da los turnos, y no era verdad, porque
`make` imprime por `stdout` el comando que ejecuta. Un `@` en el `Makefile` lo
arregló. Se añadió también `ARGS` para pasar opciones
(`make run MAP=… ARGS="--metrics"`) y un objetivo nuevo, `make bench`.

---

## 7. La prueba de la entrega

La checklist de la guía pide probar en un **clon limpio**, porque es ahí donde
aparecen los ficheros que nunca se añadieron o las dependencias implícitas. Se
copiaron los ficheros del repositorio (sin `.venv`) a un directorio vacío y se
ejecutó todo desde cero:

| Paso | Resultado |
|---|---|
| `make install` | ✅ |
| `make test` | ✅ 411 tests |
| `make lint-strict` | ✅ sin avisos en 40 ficheros |
| pygame desde `pyproject.toml` | ✅ `make install` instala `pygame-ce`, la única dependencia de ejecución |

La prueba en limpio es la que descubre las dependencias implícitas: algo que
funciona en tu máquina porque lo instalaste a mano y nadie más tiene. Por eso
pygame está declarado en `dependencies` y no se da por supuesto.

---

## 8. Preparar la evaluación

El Cap. X avisa de que pueden pedir explicar el código o modificarlo en vivo.
Cada pregunta probable tiene su respuesta escrita en la documentación:

| Pregunta | Dónde está la respuesta |
|---|---|
| ¿Por qué `(zona, turno)` y no solo `zona`? | Narrativa SP06–SP07, §1 y §4.1 |
| ¿Por qué WHCA\* y no CA\*? ¿Qué pierdes con la ventana? | [`04-algoritmo.md`](./04-algoritmo.md); SP07 |
| ¿Por qué la heurística es admisible? | SP05; narrativa SP06–SP07, §4.2 |
| ¿Por qué dos fases en el simulador? | Narrativa SP08, §4.2 |
| ¿Dónde falla el algoritmo y por qué? | SP07 (`swap_corridor.txt`); narrativa SP08, §8 |
| ¿Por qué 15 turnos en medium/02? | Esta narrativa, §5 |
| La complejidad de cada pieza | `README.md`, *Algorithm* |

Y los cambios más probables tienen un único sitio donde tocar:

| Cambio | Dónde |
|---|---|
| Un tipo de zona nuevo | `ZoneType` y `MOVEMENT_COST` en `models/zone.py` (+ su color en `pygame_view.TYPE_COLOR`) |
| Otro criterio de prioridad | Una función `(drones, turno) → lista` pasada como `order=`; se compara con `make bench` añadiéndola a `ORDERS` |
| La lectura permisiva de `restricted` | `can_move` y `reserve_move` en `reservation_table.py` (la sección 5 lo hizo así) |
| El formato de salida | `output/formatter.py` |

---

## 9. Lo que queda fuera

- **Optimalidad garantizada.** WHCA\* es voraz entre drones. En los diez mapas
  oficiales el resultado es óptimo o coincide con la referencia, pero no hay
  garantía general.
- **Los mapas de evaluación.** Pueden ser otros. La defensa es no haber
  ajustado nada a un mapa concreto, y el validador de invariantes de SP08, que
  comprueba la legalidad de cualquier traza.

---

## 10. Resumen: quién hace qué

| Pieza | Responsabilidad | Regla del subject |
|---|---|---|
| `Metrics` | Las métricas secundarias, leídas de la traza | Cap. VII.6 |
| `BENCHMARKS` / `BenchmarkSuite.target_for` | Objetivos oficiales; PAR de la visualización | Cap. VII.7 |
| `make bench` | Medición repetible: tabla oficial y comparación de configuraciones | Cap. VII.1 (eficiencia) |
| `README.md` | Entrega en inglés con la primera línea literal y las secciones exigidas | Cap. VIII |
| `pyproject.toml` (`dependencies`) y `Makefile` (`@`, `ARGS`, `bench`) | Que funcione en un clon limpio y que `stdout` sea contable | Cap. X |

Fin de la historia: del mapa en texto a los drones entregados, turno a turno.
