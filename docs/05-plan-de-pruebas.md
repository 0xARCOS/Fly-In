# Plan de pruebas

Los tests **no se entregan ni se puntúan** *(Cap. III.3 del subject)*. Existen
por dos razones muy prácticas:

1. Son la única forma de saber si una pieza funciona **antes** de montarla sobre
   las siguientes. Sin ellos, un bug de SP05 lo descubres depurando SP07.
2. En la evaluación pueden pedirte **modificar el proyecto en vivo** *(Cap. X)*.
   Con la suite verde, un cambio se valida en 3 segundos; sin ella, es una
   apuesta delante del evaluador.

Ejecuta todo con `make test`.

---

## 1. Qué prueba cada subproyecto

| Archivo de test | Subproyecto | Qué verifica |
|---|---|---|
| `test/test_parser.py` | [SP02](./build/SP02-parser.md) | Cada mapa de error falla con su causa; los válidos y los oficiales parsean; metadatos estrictos; índices de `Graph` ✅ |
| `test/test_cli.py` | [SP03](./build/SP03-cli-y-errores.md) | Fichero inexistente / sin permisos / vacío dan mensaje limpio y código de salida ≠ 0, nunca un traceback; `end_hub` inalcanzable se detecta; `--window` ≤ 0 se rechaza ✅ |
| `test/test_dijkstra.py` | [SP04](./build/SP04-dijkstra.md) | Ruta conocida a mano; `blocked` nunca aparece; `priority` gana los empates; grafo sin ruta devuelve "sin ruta", no excepción ✅ |
| `test/test_abstract_distance.py` | [SP05](./build/SP05-heuristica-abstracta.md) | `h(end)==0`; `restricted` suma 2; zona aislada es inalcanzable; coincide con Dijkstra ✅ |
| `test/test_reservation_table.py` | [SP06](./build/SP06-tabla-reservas.md) | Capacidades de zona y enlace; `start`/`end` sin límite; tránsito ocupa 2 turnos; `would_swap`; `clear_from` |
| `test/test_whca.py` | [SP07](./build/SP07-whca.md) | Un dron replica a Dijkstra; dos drones ante un cuello de botella se alternan; ruta parcial al agotar la ventana |
| `test/test_simulator.py` | [SP08](./build/SP08-drone-y-simulador.md) | Todos llegan; ninguna ocupación violada en ningún turno; el resultado no depende del orden de la lista de drones |
| `test/test_output_format.py` | [SP09](./build/SP09-formato-salida.md) | Formato exacto de línea; drones quietos omitidos; entregados dejan de aparecer; tránsito imprime la conexión |

---

## 2. Mapas de prueba

### Ya existen

| Mapa | Para qué |
|---|---|
| `maps/valid/linear.txt` | Caso feliz: 4 zonas en línea, 2 drones. El "hola mundo" del proyecto |
| `maps/valid/bottleneck.txt` | Cuello de botella deliberado: `narrow` con `max_drones=1` y ambas conexiones a capacidad 1, 3 drones. **El mapa clave de SP07** |
| `maps/valid/single_drone.txt` | Mínimo absoluto: `start-goal`, 1 dron. Aísla bugs de simulación de bugs de coordinación |
| `maps/errors/*.txt` (10) | Uno por regla de validación del parser. Ver [`03-formato-datos.md`](./03-formato-datos.md#reglas-de-validación--el-checklist-del-parser) |

### Por crear

Van en `maps/valid/` conforme los vayas necesitando. Cada uno existe para
estresar **una** propiedad concreta:

| Mapa | Nace en | Qué estresa |
|---|---|---|
| `restricted_chain.txt` | SP04 | Ruta obligada por varias `restricted` seguidas: el coste total debe ser 2 por cada una |
| `blocked_detour.txt` | SP04 | La ruta corta está cerrada por una `blocked`; el algoritmo debe rodearla |
| `priority_tie.txt` | SP04 | Dos rutas de coste idéntico, una con más `priority`: debe elegir esa |
| `dead_end.txt` | SP05 | Callejón sin salida: con heurística euclídea el dron entra; con la abstracta, no. **Demuestra por qué la heurística importa** |
| `two_corridors.txt` | SP07 | Dos rutas paralelas de igual coste: los drones deben repartirse, no hacer cola |
| `swap_corridor.txt` | SP07 | Pasillo de una zona con dos drones en sentidos opuestos: el caso patológico documentado de WHCA\* |
| `wide_graph.txt` | SP11 | Muchos drones, grafo ancho con alternativas: mide el reparto de carga y el tiempo de cálculo |

⚠️ **Escribe la salida esperada a mano antes de programar el mapa.** Si no
puedes calcular a mano cuántos turnos debería costar `bottleneck.txt`, no vas a
poder decidir si el resultado de tu algoritmo es correcto o simplemente
plausible.

---

## 3. Matriz de benchmarks oficiales *(Cap. VII.7)*

Se rellena en [SP11](./build/SP11-benchmarks-y-readme.md), ejecutando cada mapa
de referencia del subject. Anota también el tiempo de cálculo: el subject
pregunta por eficiencia, no solo por turnos.

| Categoría | Mapa | Drones | Objetivo | Turnos obtenidos | Tiempo | ¿Cumple? |
|---|---|---|---|---|---|---|
| Fácil | Linear path | 2 | ≤ 6 | | | |
| Fácil | Simple fork | 4 | ≤ 8 | | | |
| Fácil | Basic capacity | 4 | ≤ 6 | | | |
| Media | Dead end trap | 5 | ≤ 12 | | | |
| Media | Circular loop | 6 | ≤ 15 | | | |
| Media | Priority puzzle | 5 | ≤ 12 | | | |
| Difícil | Maze nightmare | 8 | ≤ 30 | | | |
| Difícil | Capacity hell | 12 | ≤ 35 | | | |
| Difícil | Ultimate challenge | 15 | ≤ 45 | | | |
| Bonus | The Impossible Dream | 25 | batir 45 | | | |

### Comparativa de parámetros

La tabla que de verdad impresiona en la review. Ejecuta los mapas difíciles con
varias configuraciones y anota:

| Mapa | `W`=8, orden por ID | `W`=8, orden por `h` | `W`=16, orden por `h` |
|---|---|---|---|
| Maze nightmare | | | |
| Capacity hell | | | |
| Ultimate challenge | | | |

Rellenarla te da la frase exacta que responde a *"¿qué optimizaciones
implementaste?"*.

---

## 4. Verificación de invariantes — el test que más bugs caza

Además de los tests por pieza, escribe **un validador independiente** del
simulador: una función que recibe la traza completa de la simulación y el grafo,
y comprueba que en **ningún** turno se violó ninguna regla:

```python
def assert_simulation_is_legal(graph: Graph, trace: list[list[Move]]) -> None:
    """Recorre la traza y verifica todas las reglas del Cap. VII.2 y VII.3.

    - Ninguna zona excede max_drones (salvo start_hub / end_hub)
    - Ninguna conexión excede max_link_capacity
    - Ningún dron entra en una zona blocked
    - Todo movimiento va entre zonas realmente conectadas
    - Todo tránsito a restricted dura exactamente 2 turnos y no se interrumpe
    - Ningún dron aparece dos veces en el mismo turno
    """
```

⚠️ **Escríbelo con lógica independiente de la del simulador.** Si reutiliza la
`ReservationTable`, solo comprueba que la tabla es consistente consigo misma —
que es justo lo que no quieres saber. Este validador debe leer la traza como si
fuera un evaluador externo que solo conoce el grafo y las reglas del PDF.

Aplícalo a **todos** los mapas en un test parametrizado: es una red que caza
regresiones en SP07, SP08 y SP09 de una sola vez.

---

## 5. Métricas secundarias

El subject las menciona como opcionales pero recomendadas *(Cap. VII.6)*, y
sirven de desempate si tu recuento de turnos coincide con el de otro compañero:

- Drones movidos por turno (promedio) — eficiencia del reparto de rutas
- Turnos promedio por dron
- Coste total de ruta (suma de costes ponderados de todos los drones)

Imprímelas por `stderr` al final de la simulación, para no ensuciar el formato
de salida de `stdout` (ver [`03-formato-datos.md`](./03-formato-datos.md)).
