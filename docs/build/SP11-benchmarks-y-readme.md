# SP11 — Benchmarks, ajuste y `README.md` ✅

**Objetivo:** medir contra los objetivos del subject, ajustar los parámetros con
datos, y escribir el `README.md` que se entrega.

**Prerequisitos:** [SP09](./SP09-formato-salida.md) y
[SP10](./SP10-visualizacion.md) verdes.

**Criterio de salida:** cumples (o justificas razonadamente) la tabla de
benchmarks, y un compañero puede clonar el repo, seguir el `README.md` y
ejecutar la simulación sin preguntarte nada.

---

## Parte A — Medir

### Paso 1 — Un runner de benchmarks

Un script que ejecute todos los mapas y vuelque una tabla. No tiene que ser
elegante; tiene que ser **repetible**, porque lo vas a ejecutar veinte veces
mientras ajustas.

```console
$ make bench
mapa                    drones  W  orden  turnos  objetivo  ok   tiempo
easy/01_linear           2      8  h      5       ≤6        ✅   0.01s
easy/02_fork             4      8  h      7       ≤8        ✅   0.02s
medium/01_deadend        5      8  h      14      ≤12       ❌   0.09s
...
```

Mide **turnos y tiempo**. El subject pregunta explícitamente por eficiencia,
complejidad y uso de memoria *(Cap. VII.1)*, no solo por el recuento de turnos.

### Paso 2 — Rellenar la matriz oficial

En [`05-plan-de-pruebas.md`](../05-plan-de-pruebas.md#3-matriz-de-benchmarks-oficiales-cap-vii7).

| Categoría | Mapa | Drones | Objetivo |
|---|---|---|---|
| Fácil | Linear path | 2 | ≤ 6 |
| Fácil | Simple fork | 4 | ≤ 8 |
| Fácil | Basic capacity | 4 | ≤ 6 |
| Media | Dead end trap | 5 | ≤ 12 |
| Media | Circular loop | 6 | ≤ 15 |
| Media | Priority puzzle | 5 | ≤ 12 |
| Difícil | Maze nightmare | 8 | ≤ 30 |
| Difícil | Capacity hell | 12 | ≤ 35 |
| Difícil | Ultimate challenge | 15 | ≤ 45 |

### Paso 3 — Ajustar con datos, no a ojo

Las dos palancas son `W` y el criterio de prioridad
([SP07](./SP07-whca.md#paso-6--el-orden-de-planificación)). Ejecuta la matriz
completa con varias combinaciones:

| Mapa | W=8, ID | W=8, h desc | W=16, h desc | W=16, rotatorio |
|---|---|---|---|---|
| Maze nightmare | | | | |
| Capacity hell | | | | |
| Ultimate challenge | | | | |

⚠️ **No lo des por sentado — no ajustes contra un mapa concreto**
*(Cap. X)*: *"Evaluation maps may be different from the ones provided in the
subject."* Si tocas la heurística hasta que "Capacity hell" salga en 34 turnos,
habrás sobreajustado a ese mapa y fallarás en el de evaluación. Ajusta
**parámetros globales** (`W`, orden de prioridad) y quédate con la configuración
que va mejor **de media** en las tres categorías.

⚠️ **No lo des por sentado — si no llegas al objetivo, mide antes de tocar nada**
Averigua **dónde** se pierden los turnos: ¿hay drones esperando mucho en
`start_hub`? ¿Todos usan la misma ruta pudiendo repartirse? ¿El cuello de
botella está saturado o hay capacidad sin usar? Imprime la ocupación por turno y
mira. Tocar `W` a ciegas es una ruleta; entender dónde está la pérdida te da la
frase exacta que quieres decir en la review.

### Paso 4 — Las métricas secundarias

*(Cap. VII.6)*, opcionales pero recomendadas. Sirven de desempate si tu recuento
de turnos coincide con el de otro compañero:

- drones movidos por turno (promedio) — eficiencia del reparto,
- turnos promedio por dron,
- coste total de ruta (suma ponderada de todos los drones).

Van por `stderr` con `--metrics`, para no ensuciar `stdout`.

---

## Parte B — El `README.md`

**En inglés**, obligatoriamente *(Cap. VIII)*, en la raíz del repositorio.

### La primera línea es literal

```markdown
*This project has been created as part of the 42 curriculum by <tu_login>.*
```

En cursiva, y **la primera línea del archivo**. El subject es explícito.

### Secciones exigidas

| Sección | Qué debe contener |
|---|---|
| **Description** | Qué es el proyecto, su objetivo y una visión general breve |
| **Instructions** | Compilación, instalación, ejecución. `make install`, `make run MAP=...`, versión de Python |
| **Resources** | Referencias clásicas del tema (el paper de Silver, documentación) **y cómo se usó la IA: para qué tareas y en qué partes del proyecto** |
| **Algorithm** | Descripción detallada de tus decisiones de algoritmo y tu estrategia de implementación |
| **Visual representation** | Qué muestra y **cómo mejora la experiencia** |
| **Example** | Una entrada de ejemplo con su salida esperada |

⚠️ **No lo des por sentado — la mención de la IA es obligatoria y específica**
*(Cap. VIII)*: *"as well as a description of how AI was used — specifying for
which tasks and which parts of the project."* No vale "usé IA para ayudarme". Di
qué: *"para redactar la documentación de `docs/`, para revisar la lógica del
parser, para explicar el paper de Silver"*. El Cap. II es tajante al respecto:
*"Only use AI-generated content that you fully understand and can take
responsibility for"*, y en la evaluación pueden pedirte explicar cualquier línea.

### Qué añadir aunque no lo pidan

Lo que de verdad distingue un README bueno:

- **La tabla de benchmarks con tus resultados reales.** Es la prueba objetiva de
  que tu algoritmo funciona.
- **La comparación de configuraciones** (`W`=8 vs 16, orden por ID vs por `h`).
  Responde por adelantado a *"¿qué optimizaciones implementaste?"*.
- **Las limitaciones conocidas.** WHCA\* no es completo ni óptimo: di dónde falla
  y enseña el contraexemplo (`swap_corridor.txt`). Conocer los límites de tu
  propia solución es de las cosas que mejor demuestran que la entiendes.
- **Una captura de la visualización.**

---

## Parte C — El pulido final

### La checklist de entrega

- [ ] `make install` funciona **en un clon limpio**. Pruébalo de verdad:
      `git clone` en `/tmp` y ejecuta. Es donde aparecen los archivos que
      tenías en local y nunca commiteaste
- [ ] `make lint` y `make lint-strict` sin errores
- [ ] `make test` verde
- [ ] `make clean` deja el repo como recién clonado
- [ ] Sin código muerto, sin `print()` de depuración olvidados
- [ ] Docstrings PEP 257 en todas las clases y funciones públicas *(Cap. III.1)*
- [ ] Type hints completos
- [ ] Ningún input produce un traceback — reprueba los casos de
      [SP03](./SP03-cli-y-errores.md)
- [ ] **Todos los archivos en la raíz del repositorio** *(Cap. X, aviso en rojo)*
- [ ] `.gitignore` efectivo: `git status` limpio tras ejecutar todo

### Prepara la evaluación

*(Cap. X)*: *"we may ask you to explain your code or possibly even to write some
code"* y *"a brief modification of the project may occasionally be requested"*.

Ensaya en voz alta:

- Por qué `(zona, turno)` y no solo `zona`
- Por qué WHCA\* y no CA\* — y qué pierdes con la ventana
- Por qué la heurística es admisible
- Por qué el simulador tiene dos fases
- Dónde falla tu algoritmo y por qué
- La complejidad de cada pieza

Y ten localizado dónde tocarías para los cambios más probables: añadir un tipo
de zona nuevo, cambiar el criterio de prioridad, cambiar el formato de salida.
Si tu arquitectura es buena, cada uno es un sitio único; si te descubres diciendo
"habría que tocar en cuatro archivos", esa es información valiosa sobre tu propio
diseño.

---

## Criterio de salida

- [x] Matriz de benchmarks rellena, con resultados reales
- [x] Configuración elegida justificada con datos
- [x] `README.md` completo, en inglés, con la primera línea literal
- [x] Checklist de entrega completa
- [x] Un compañero clona, sigue el README y ejecuta sin preguntarte nada

## Decisiones tomadas

Runner en `fly_in/benchmarks.py` (`make bench`), métricas en
`fly_in/simulation/metrics.py` (`--metrics`), probado en
`test/test_metrics.py` (15 tests). `README.md` reescrito en inglés. La
historia completa está en [`12-narrativa-sp11.md`](../12-narrativa-sp11.md).

**Resultados** (W = 8, orden por id): los 10 mapas cumplen.

| Categoría | Mapa | Drones | Objetivo | Turnos | Tiempo |
|---|---|---|---|---|---|
| Fácil | Linear path | 2 | ≤ 6 | 4 | < 1 ms |
| Fácil | Simple fork | 4 | ≤ 8 | 4 | 1 ms |
| Fácil | Basic capacity | 4 | ≤ 6 | 4 | < 1 ms |
| Media | Dead end trap | 5 | ≤ 12 | 8 | 1 ms |
| Media | Circular loop | 6 | ≤ 15 | 15 | 6 ms |
| Media | Priority puzzle | 5 | ≤ 12 | 7 | 1 ms |
| Difícil | Maze nightmare | 8 | ≤ 30 | 13 | 10 ms |
| Difícil | Capacity hell | 12 | ≤ 35 | 16 | 23 ms |
| Difícil | Ultimate challenge | 15 | ≤ 45 | 26 | 76 ms |
| Bonus | The Impossible Dream | 25 | batir 45 | 43 | 247 ms |

**Comparación de configuraciones** (turnos totales en los 10 mapas):

| | id | nearest | farthest | rotating |
|---|---|---|---|---|
| W = 4 | 140 | 140 | 230 | 170 |
| W = 8 | 140 | 140 | 266 | 177 |
| W = 16 | 140 | 140 | 276 | 207 |

| Decisión | Por qué |
|---|---|
| Orden **por id** | Empata con `nearest_first` en los 10 mapas y es el más simple de explicar. `farthest_first` pierde por la reserva provisional de SP07 (el de detrás planifica primero y ve al de delante quieto); `rotating` rompe la fila que forman los drones al salir de `start_hub` |
| **W = 8** | W no cambia los turnos entre 4 y 16 con los mejores órdenes; 8 deja margen para topologías más retorcidas que las de los mapas oficiales sin coste apreciable (0,25 s el challenger) |
| No se ajusta nada a un mapa concreto | Cap. X: los mapas de evaluación pueden ser otros. Solo se tocaron parámetros globales |
| medium/02 con 15 turnos (justo el objetivo) | Es el óptimo con la lectura estricta de `restricted` (SP06): la conexión `loop_b-exit_point` (capacidad 1) admite un dron cada 2 turnos |
| Métricas: turnos, movimientos, esperas, movimientos por turno, turno medio de entrega, pico en el aire, tiempo | Las pide el Cap. VII.6 como desempate; se calculan desde la traza, no desde el estado interno |
| El `Makefile` como pantalla de carga: `make` abre un menú principal y cada target muestra fases animadas con consejos (`scripts/loading.sh`) | La interfaz va entera a `stderr` y cae a texto plano sin terminal o con `NO_COLOR`: `stdout` y los códigos de salida no cambian, y los comandos reales siguen escritos en el `Makefile` |
| El login del `README.md` es `ariarcos` | Es el usuario del sistema; **confírmalo** antes de entregar |

**Checklist de entrega:** `make install`, `make test`, `make lint` y
`make lint-strict` verificados en una copia limpia del repositorio;
`make install` instala `pygame-ce`; ningún input produce traceback; `make
clean` borra las cachés.
