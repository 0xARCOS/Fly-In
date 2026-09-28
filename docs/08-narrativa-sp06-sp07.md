# SP06 y SP07 contados de principio a fin

Los documentos de [`build/`](./build/) son guías de construcción: pasos,
contratos, avisos y tests. Este es otra cosa. Cuenta **como una sola historia**
lo que hacen la tabla de reservas ([SP06](./build/SP06-tabla-reservas.md)) y la
búsqueda cooperativa ([SP07](./build/SP07-whca.md)): qué regla del subject
obliga a que exista cada pieza, por qué cada función tiene la forma que tiene y
qué cambia en la ejecución del programa por culpa de ella.

> **Estado.** SP06 está implementado en
> [`fly_in/pathfinding/reservation_table.py`](../fly_in/pathfinding/reservation_table.py)
> y cubierto por
> [`test/test_reservation_table.py`](../test/test_reservation_table.py). SP07
> todavía no tiene código: su parte describe el diseño cerrado en
> [`SP07-whca.md`](./build/SP07-whca.md), que es el que se va a implementar.

---

## 1. El problema que ninguno de los dos resuelve por separado

El subject pide mover **todos** los drones desde `start_hub` hasta `end_hub` en
el menor número de turnos posible *(Cap. VII)*. La palabra que lo complica todo
es *todos*. Con un dron, el problema está resuelto desde SP04: Dijkstra da la
ruta más barata y no hay nada más que pensar. Con varios drones aparecen las
reglas de ocupación del Cap. VII.2: una zona admite como mucho `max_drones`
drones a la vez (uno por defecto), una conexión como mucho `max_link_capacity`,
y dos drones no pueden entrar en la misma zona el mismo turno si no caben.

Si cada dron sigue su ruta de Dijkstra sin mirar a los demás, todos eligen el
mismo camino, porque todos calculan lo mismo sobre el mismo grafo. En
[`bottleneck.txt`](../maps/valid/bottleneck.txt) —tres drones, un único paso
`start → narrow → goal`, con `narrow` de capacidad 1— los tres querrían entrar
en `narrow` en el primer turno. Dos de esas tres entradas son ilegales.

Hace falta, por tanto, algo que **recuerde lo que ya han decidido los demás**
y algo que **busque rutas teniéndolo en cuenta**. Lo primero es la tabla de
reservas (SP06). Lo segundo es la búsqueda WHCA\* (SP07). Ninguno sirve sin el
otro: una tabla sin nadie que la consulte es un diccionario muerto, y una
búsqueda sin tabla es otra vez Dijkstra.

La idea que los une viene del artículo de Silver (2005) y está explicada en
[`04-algoritmo.md`](./04-algoritmo.md): si el estado de la búsqueda deja de ser
`zona` y pasa a ser `(zona, turno)`, entonces "el dron 1 estará en `narrow` en
el turno 1" es un obstáculo igual que una zona `blocked`, solo que dura un
turno. La búsqueda no tiene que *detectar* colisiones: las colisiones
simplemente no están entre los estados a los que puede llegar. La tabla de
reservas es la que dice qué estados están tachados.

---

## 2. Antes de nada: qué significa "turno"

Las dos piezas hablan de turnos todo el rato, y el error más caro de este tramo
del proyecto es que cada una entienda una cosa distinta por "el turno 3". Por
eso la convención está escrita en la cabecera de `reservation_table.py` y SP07 y
SP08 la heredan tal cual.

El **instante `t`** es la foto del mundo después de ejecutar `t` turnos. El
instante 0 es la foto inicial, con todos los drones en `start_hub`. La línea
`k` de la salida del programa describe el paso del instante `k-1` al instante
`k`. Con esto:

- **Una zona en el instante `t`** contiene a los drones que están en ella en esa
  foto.
- **Una conexión en el instante `t`** contiene a los drones que la están
  cruzando *entre* la foto `t` y la foto `t+1`.
- **Un movimiento que sale en `T` con coste `c`** ocupa la conexión en los
  instantes `T … T+c-1` y la zona de destino en el instante `T+c`. Entre medias
  no ocupa ninguna zona.

La última frase es la traducción directa de la regla `restricted` del Cap.
VII.3: entrar en una zona `restricted` cuesta dos turnos, el dron ocupa la
conexión mientras tanto y *debe* llegar al turno siguiente, sin posibilidad de
quedarse en el aire. Con coste 1 la misma fórmula da el caso normal: conexión en
`T`, zona en `T+1`.

Hay una regla del subject que esta convención cumple sin escribir una sola
línea para ella: *"Drones moving out of a zone free up capacity for that same
turn"*. Un dron que sale de `narrow` en el instante 1 está en `(narrow, 1)`,
pero no en `(narrow, 2)`. Otro dron que entra en `narrow` saliendo también en el
instante 1 llega en el instante 2, que es exactamente la casilla que se
comprueba. Los dos se cruzan limpiamente sin que nadie haya tenido que
programar "las salidas se cuentan antes que las entradas".

---

## 3. SP06 — La tabla de reservas

### 3.1 Qué se guarda, y por qué en tres sitios

`ReservationTable` guarda tres diccionarios, y cada uno existe para hacer
cumplir una regla distinta:

| Diccionario | Clave | Regla que protege |
|---|---|---|
| `_zones` | `(nombre_zona, instante)` | `max_drones` (Cap. VII.2) |
| `_links` | `(nombre_conexión, instante)` | `max_link_capacity` (Cap. VII.2) y la ocupación de la conexión durante un tránsito `restricted` (Cap. VII.3) |
| `_moves` | `(origen, destino, instante)` | Que dos drones no se crucen de frente por la misma conexión |

Los dos primeros salen literalmente del subject. El tercero es una decisión de
diseño propia, y merece contarse con calma porque es la que un evaluador va a
preguntar.

Imagina una conexión `a-b` con `max_link_capacity=2`. El dron 1 va de `a` a
`b`; el dron 2, de `b` a `a`, en el mismo turno. Contando drones, caben: son
dos y el límite es dos. Pero físicamente se atravesarían. En la literatura MAPF
esto se llama *edge conflict*, y no se puede detectar contando: hay que saber
**en qué dirección** va cada uno. El subject no lo prohíbe explícitamente, pero
tampoco lo permite; decidimos que la simulación sea físicamente coherente y
guardamos el sentido de cada movimiento en `_moves`.

En los tres diccionarios el valor no es un número sino una **lista de ids de
dron**. La ocupación es la longitud de la lista. Guardar *quién* y no solo
*cuántos* cuesta prácticamente lo mismo y habilita dos cosas: que `clear_from`
pueda conservar las reservas de unos drones concretos (sección 3.4) y que al
depurar se pueda preguntar "¿quién está en `narrow` en el instante 5?" y
obtener una respuesta útil.

Las claves usan el **nombre** de la zona o conexión, no el objeto. Funcionaría
con objetos (hashean por identidad), pero un volcado de la tabla con nombres
se lee a simple vista, y los nombres son únicos por construcción: el parser
rechaza zonas repetidas y conexiones duplicadas, y como los nombres de zona no
pueden llevar guiones, `a-b` identifica una sola conexión.

### 3.2 Las preguntas

La tabla responde a preguntas antes de escribir nada. La búsqueda de SP07 se
pasa la vida haciéndoselas, así que son el punto de contacto real entre las dos
piezas.

**`zone_has_room(zone, turn)`** responde "¿cabe un dron más en esta zona en este
instante?". Compara el número de ocupantes con `zone.max_drones`. Lo
interesante es lo que *no* hace: no pregunta si la zona es `start_hub` o
`end_hub`. El subject dice que esas dos zonas no tienen límite *(Cap. VII.2)*,
y eso ya lo resolvió el parser en SP02 dándoles `max_drones = UNLIMITED`, que es
`float("inf")`. Cualquier número es menor que infinito, así que la comparación
genérica es cierta para ellas sin un solo `if`. Si alguien añadiera además un
`if zone is start_hub`, habría dos mecanismos para la misma regla y tarde o
temprano divergirían.

El efecto en la ejecución es enorme, aunque invisible cuando funciona. Si
`start_hub` tuviera capacidad 1 en la tabla, con cinco drones el segundo ya no
podría ni "esperar en casa" en el instante 1, y lo que se vería desde fuera
sería "el dron 2 no encuentra ruta": un síntoma en SP07 de un fallo que en
realidad está aquí. El test `test_start_and_end_never_fill_up` mete cien drones
en cada hub precisamente para blindar esto frente a cambios futuros del parser.

**`link_has_room(conn, turn)`** es lo mismo para conexiones: ¿hay sitio para un
dron más cruzando `conn` entre el instante `turn` y el siguiente? Aquí no hay
excepción posible: aunque `end_hub` tenga capacidad infinita, la conexión que
lleva a él no la tiene, y el test `test_end_hub_is_unlimited_but_its_connection_is_not`
lo fija. En `bottleneck.txt` es justo esto lo que obliga a los drones a salir
de uno en uno: `start` los admite a todos, pero `start-narrow` solo deja pasar
uno por turno.

**`would_swap(frm, to, turn)`** responde "¿hay alguien cruzando esta conexión
en sentido contrario en este instante?". Es una sola consulta al diccionario
`_moves` con la clave invertida `(to, frm, turn)`. Como un tránsito
`restricted` apunta su sentido en *cada* instante del trayecto, el cruce se
detecta también en el segundo turno: si el dron 1 sale hacia una `restricted`
en `T` y el dron 2 intenta entrar en la misma conexión desde el otro lado en
`T+1`, `would_swap` lo ve.

**`can_move(frm, to, turn)`** es la pregunta importante, la única que SP07
necesita hacer para un movimiento. Junta todas las anteriores en el orden
correcto:

1. Busca la conexión entre `frm` y `to` con `graph.connection_between`. Si no
   existe, lanza `ValueError`: preguntar por un movimiento entre zonas no
   conectadas es un error del que llama, no un "no".
2. Si `to` es `blocked`, devuelve `False`. Tiene que ir antes del siguiente paso
   porque `movement_cost()` lanza una excepción para zonas `blocked`.
3. Deduce el coste de la zona de destino (1 o 2), porque el subject dice que el
   coste lo fija siempre el tipo del destino.
4. Para cada instante del trayecto, `range(turn, turn + cost)`, comprueba que la
   conexión tiene sitio y que nadie viene de frente.
5. Comprueba que la zona de destino tiene sitio en el instante de llegada,
   `turn + cost`.

La razón de que exista `can_move`, en vez de dejar que SP07 llame a las cuatro
consultas sueltas, es que es muy fácil olvidarse de una. Una búsqueda que
comprobara la zona de destino pero no la conexión funcionaría en todos los
mapas de capacidad 1 —donde la zona ya limita— y fallaría solo en mapas con
zonas grandes y enlaces estrechos. Concentrar la comprobación en un sitio
convierte "las reglas de movimiento" en una única función que se prueba una
vez.

El paso 4 es el que materializa la regla `restricted`. Con coste 2, la conexión
tiene que estar libre **dos** instantes seguidos, y la zona de destino en el
instante `turn + 2`. En el instante intermedio no se consulta ninguna zona,
porque el dron no ocupa ninguna: está en el aire. Si se hubiera simplificado
dejando al dron "ocupando" su zona de origen durante el tránsito, se estaría
bloqueando una zona libre y otro dron esperaría sin motivo. El total de turnos
subiría y no habría forma sencilla de saber por qué.

**`zone_occupants` y `link_occupants`** devuelven una copia de la lista de ids.
No las usa la búsqueda —para ella basta con "¿cabe?"— sino la depuración, los
tests y, más adelante, el simulador si quiere verificar que lo que ejecuta
coincide con lo reservado. Devuelven copia para que nadie pueda modificar la
tabla desde fuera por accidente.

### 3.3 Las escrituras

Una vez que un dron ha decidido su ruta, hay que apuntarla. Para eso hay dos
operaciones, una por cada cosa que un dron puede hacer en un turno según el
Cap. VII.3: moverse o quedarse quieto.

**`reserve_move(drone_id, frm, to, turn)`** apunta que el dron sale de `frm` en
el instante `turn` hacia `to`. Primero llama a `can_move`; si no cabe, lanza
`ReservationError` sin tocar nada. Si cabe, apunta la conexión y el sentido en
cada instante del trayecto y la zona de destino en el de llegada. Es exactamente
el mismo recorrido que hizo `can_move`, esta vez escribiendo.

Tres decisiones de esta firma tienen consecuencias:

- **No recibe la conexión ni el coste.** Los deduce ella del grafo y de la zona
  de destino. Si los recibiera desde fuera, alguien podría pasar coste 1 hacia
  una `restricted`, la tabla reservaría un solo turno de conexión y el error no
  se manifestaría hasta que otro dron se colara en el segundo turno. Deducirlos
  dentro hace que esa incoherencia sea imposible de escribir.
- **Hay un único método para movimientos de coste 1 y de coste 2.** El bucle
  `range(turn, turn + cost)` cubre los dos. Dos métodos separados acabarían con
  la misma lógica duplicada y, antes o después, distinta.
- **Es atómico.** Como se pregunta todo antes de escribir nada, o se reserva el
  movimiento entero o no se reserva nada. Una tabla a medias —conexión
  reservada pero zona de llegada no— es el tipo de estado imposible que
  produce colisiones tres turnos después y muy lejos de su causa.

**`reserve_wait(drone_id, zone, turn)`** apunta que el dron está en `zone` en el
instante `turn` sin haberse movido. Es la reserva de "quedarse quieto". Existe
porque `reserve_move` solo reserva la zona de destino **en el instante de
llegada**, no los siguientes. Un dron que llega a `narrow` en el instante 1 y se
queda ahí hasta el 4 necesita tres reservas de espera más, una por instante.

Esa es otra decisión que conviene poder defender: la alternativa era que
`reserve_move` reservara la zona de destino "hasta la siguiente salida". Parece
más eficiente, pero obliga a conocer el futuro en el momento de reservar y
mezcla dos decisiones en una llamada. Con la opción elegida, la tabla es una
foto exacta de dónde está cada dron en cada instante, y quien graba la ruta
(SP07) solo tiene que recorrerla paso a paso.

Ambas escrituras pasan por el helper privado **`_add`**, que además de añadir
el id comprueba que ese dron no estuviera ya apuntado en esa misma casilla. Un
dron contado dos veces en `narrow` haría que la tabla creyera la zona llena
cuando solo hay uno, y otro dron esperaría sin motivo. Eso solo puede pasar si
alguien graba la misma ruta dos veces, que es un bug; `_add` lo convierte en
una excepción inmediata en lugar de en un turno perdido silencioso.

**`ReservationError`** es la excepción de todas estas escrituras. Existe en
lugar de devolver `False` porque un `bool` se puede ignorar sin querer y una
excepción no. En un programa correcto nunca salta: la búsqueda pregunta con
`can_move` antes de proponer un movimiento, y la ruta que graba es la misma que
preguntó. Si salta, hay un bug entre SP07 y la tabla, y es mejor enterarse en
la línea exacta que como una colisión inexplicable en la salida.

### 3.4 Olvidar el futuro: `clear_from`

Todo lo anterior bastaría si los drones planificaran una vez y para siempre.
Pero SP07 planifica solo unos pocos turnos por delante (la *ventana*), y SP08
vuelve a planificar periódicamente. Cada vez que lo hace, las reservas del
futuro son predicciones que ya no valen: se hicieron con información vieja. Las
del pasado, en cambio, son historia ya ejecutada.

**`clear_from(turn, keep)`** separa las dos. Descarta todas las reservas del
instante `turn` en adelante y conserva las anteriores. Lo hace en los tres
diccionarios a la vez, porque una zona liberada con su conexión aún reservada
sería otro estado imposible.

El límite es `< turn`, estrictamente: las reservas **del propio instante**
`turn` también se tiran. Es lo correcto porque los movimientos que salen en
`turn` son justo los que se van a replanificar. Si se conservaran, la búsqueda
del dron 1 encontraría la conexión que el propio dron 1 había reservado en la
planificación anterior y la esquivaría: el dron se estaría apartando de sí
mismo.

El parámetro `keep` resuelve el único caso en el que tirar el futuro es
peligroso: los drones **en el aire**. Un dron que salió hacia una `restricted`
en el instante `T-1` sigue en la conexión en `T` y aterriza en `T+1`. El
subject dice que *debe* llegar, no puede esperar en la conexión ni dar media
vuelta. Si `clear_from(T)` borrara su conexión en `T` y su zona de aterrizaje en
`T+1`, otro dron podría planificar entrar ahí, y el primero no tendría dónde
aterrizar. No hay forma de recuperarse de eso. Con `keep`, SP08 pasa los ids de
los drones en tránsito y sus reservas se conservan enteras; los demás las ven y
las esquivan, y esos drones no se replanifican en ese ciclo.

La limpieza la hace el helper privado **`_cleared`**, que construye un
diccionario nuevo en lugar de borrar entradas del existente. No es una
preferencia de estilo: borrar claves de un diccionario mientras se recorre
lanza `RuntimeError: dictionary changed size during iteration`. De paso, copia
cada lista de ocupantes, para que la tabla nueva no comparta listas con la
vieja.

---

## 4. SP07 — La búsqueda cooperativa

Con la tabla construida, SP07 tiene la pieza que le faltaba para que la
búsqueda de un dron "vea" a los demás. Su trabajo es: dado un dron, su posición
y el instante actual, encontrar la mejor ruta que no choque con nadie, mirando
como mucho `W` turnos hacia delante.

### 4.1 El estado es `(zona, turno)`

En Dijkstra, visitar una zona dos veces era desperdicio. Aquí no: estar en
`narrow` en el instante 3 y en el instante 9 son situaciones distintas, y a
veces la solución consiste precisamente en apartarse y volver. Por eso todo lo
que en SP04 se indexaba por zona se indexa aquí por la pareja, empezando por el
conjunto de estados cerrados. Cerrar solo por zona tendría un efecto doble y
desastroso: impediría volver a un sitio más tarde y, sobre todo, rompería
"esperar", porque esperar es pasar de `(z, t)` a `(z, t+1)`, y con cerrado por
zona ese estado se descartaría nada más generarse.

### 4.2 El nodo de búsqueda

Cada estado que la búsqueda mete en su cola de prioridad es un `SearchNode`:

- `f` — la estimación total, `g + h`. Va **primero** porque `@dataclass(order=True)`
  compara los campos en el orden en que están declarados, como una tupla, y el
  heap tiene que ordenar por `f`. Si `g` fuera primero, la búsqueda seguiría
  dando rutas correctas pero se comportaría como Dijkstra y exploraría muchos
  más estados: un fallo que no se ve en los resultados, solo en el tiempo.
- `g` — turnos gastados desde el inicio de la ventana.
- `turn` — el instante absoluto de simulación, que es el que se usa para
  consultar la tabla.
- `zone_name` — el nombre, no el objeto `Zone`, porque `Zone` no se puede
  comparar con `<` y rompería `order=True`.
- `tie` — un contador incremental. Si dos nodos empatan en todo lo anterior,
  Python compararía `zone_name` y desempataría por orden alfabético, que es
  arbitrario. El contador desempata a favor del nodo descubierto antes, lo que
  hace que la misma entrada produzca siempre la misma salida.

`h` es la heurística abstracta de SP05: la distancia real de cada zona a
`end_hub` ignorando a los demás drones, precalculada una sola vez con un
Dijkstra hacia atrás. Como los demás drones solo pueden retrasar, nunca
adelantar, esa distancia nunca sobreestima, y eso es lo que permite a A\*
encontrar la mejor ruta sin explorarlo todo. Además conoce la topología: una
zona desde la que no se llega al objetivo no está en su tabla
(`is_reachable` devuelve `False`), y la búsqueda ni la considera.

### 4.3 `find_path`, paso a paso

`find_path(dron, turno_inicial)` arranca con un único nodo: la zona actual del
dron en el instante actual, con `g = 0`. A partir de ahí saca siempre el nodo de
menor `f` y decide qué hacer con él, en este orden:

1. **¿Es `end_hub`?** Entonces ya está: se reconstruye la ruta hasta ahí y se
   devuelve. Esta comprobación va antes que la de la ventana a propósito: un
   dron que alcanza el objetivo justo en el último turno de la ventana ha
   llegado, no se ha "salido de la ventana".
2. **¿Se ha agotado la ventana** (`turn - turno_inicial >= W`)? Entonces el nodo
   no se expande, pero se recuerda si es el más prometedor visto hasta ahora
   (el de menor `f`). Más allá de la ventana no se coopera: se confía en `h`.
3. **¿Ya se cerró `(zona, turno)`?** Entonces se ignora. Si no, se cierra.
4. **Se generan los sucesores por conexión.** Para cada conexión de la zona, el
   vecino se descarta si es `blocked`, si no alcanza el objetivo según la
   heurística, o si `tabla.can_move(zona, vecino, turno)` dice que no. Aquí es
   donde todo el trabajo de SP06 entra en juego en una sola llamada: capacidad
   de la conexión en cada instante del trayecto, cruce de frente, capacidad de
   la zona de llegada, coste 1 o 2. Los que pasan se meten en la cola con
   `g + coste` y `turno + coste`.
5. **Se genera el sucesor "esperar".** Si `tabla.zone_has_room(zona, turno + 1)`,
   se mete `(misma zona, turno + 1)` con coste 1.

El paso 5 es el que más fácil se olvida y el que más importa. Esperar es un
movimiento legal del subject (*"Stay in place"*, Cap. VII.3) y es **el único
mecanismo por el que un dron cede el paso**. Sin él, un dron que encuentra un
pasillo ocupado durante un turno no tiene ningún sucesor, la búsqueda se queda
sin nodos y concluye que no hay ruta. El síntoma engaña: todo funciona con un
dron y falla en cuanto hay dos. Y como `start_hub` tiene capacidad infinita,
esperar en casa siempre es posible; es lo que harán casi todos los drones en los
primeros turnos de un mapa con cuello de botella.

Si la cola se vacía sin haber llegado al objetivo, se devuelve la ruta hasta el
nodo más prometedor que tocó el borde de la ventana. Que la ventana se agote
**no es un fracaso**: es el funcionamiento normal de WHCA\*. El dron ejecutará
esa ruta parcial, y en la siguiente replanificación obtendrá la continuación
con información más fresca. Solo si no se alcanzó ni siquiera el borde —el dron
está completamente encerrado ahora mismo— no hay ruta que devolver, y aun así
la respuesta no es `None` sino "quédate donde estás": una ruta de un paso. Así
el simulador nunca recibe un dron sin instrucciones.

### 4.4 Lo que devuelve: `Step`

Una ruta no es una lista de zonas, porque el simulador y la salida necesitan
más: cada `Step` lleva la zona donde acaba, el instante absoluto de llegada, la
conexión por la que pasa (o `None` si es una espera) y su coste. Con eso, SP08
sabe cuándo ejecutar cada paso y SP09 sabe qué imprimir: en un tránsito
`restricted`, la línea del primer turno nombra la conexión (`D1-start-r1`) y la
del segundo la zona (`D1-r1`). Todo eso ya lo sabía la búsqueda; tirarlo y
reconstruirlo después sería una segunda fuente de errores.

### 4.5 Grabar la ruta

En cuanto un dron termina de planificar, su ruta se graba en la tabla **antes**
de que planifique el siguiente. Cada paso con conexión se convierte en un
`reserve_move` que sale en `llegada - coste`, y cada espera en un
`reserve_wait`. Si se olvidara este paso, todos los drones planificarían contra
la misma tabla vacía y obtendrían la misma ruta: la cooperación desaparece y se
vuelve al problema de la sección 1.

Aquí se cierra el círculo con SP06. La búsqueda aceptó cada movimiento porque
`can_move` dijo que sí; al grabarlo, `reserve_move` vuelve a preguntar a
`can_move` sobre la misma tabla. Si la respuesta cambiara —porque la búsqueda y
la grabación no estuvieran de acuerdo sobre el instante de salida, por ejemplo—
saltaría `ReservationError` en el acto. Es el desfase de ±1 del que avisa la
convención de tiempo, detectado en el momento en que se produce.

### 4.6 Quién planifica primero

Los drones planifican de uno en uno, y el primero se lleva las mejores
reservas. El orden, por tanto, afecta al resultado. Ordenar por id es
determinista pero favorece siempre al dron 1; ordenar por `h` descendente deja
elegir primero a los que están más lejos, lo que suele reducir el turno del
último en llegar, que es precisamente la métrica del subject. Por eso el
criterio se diseña como un parámetro intercambiable: la comparación entre
criterios se hará con datos en SP11, no a ojo.

---

## 5. Todo junto: cómo se ve en la ejecución

SP08 es el director: cada `W/2` turnos llama a `clear_from`, pide a SP07 una
ruta para cada dron en orden de prioridad y la graba; entre replanificaciones,
ejecuta lo planificado. Veamos qué producen las dos piezas en los mapas de
ejemplo.

### 5.1 `bottleneck.txt`: tres drones, un paso estrecho

`start` y `goal` tienen capacidad ilimitada; `narrow` y las dos conexiones,
capacidad 1.

**Dron 1** planifica sobre la tabla vacía. Nadie le estorba: sale en 0 hacia
`narrow` y en 1 hacia `goal`. Al grabar, la tabla apunta `start-narrow` en 0,
`narrow` en 1, `narrow-goal` en 1 y `goal` en 2.

**Dron 2** planifica después. En el instante 0, `can_move(start, narrow, 0)`
dice que no: la conexión ya lleva al dron 1. Su único sucesor es esperar, y
`zone_has_room(start, 1)` es cierto porque `start` es ilimitada. En el instante
1, `can_move(start, narrow, 1)` sí pasa: la conexión está libre en 1 y `narrow`
está libre en 2, porque el dron 1 ocupa `narrow` en el instante 1 pero se va en
ese mismo turno. Aquí se ve la regla "las salidas liberan capacidad en el mismo
turno" funcionando sola, sin código específico. El dron 2 llega a `goal` en 3.

**Dron 3** repite el razonamiento un turno más tarde: espera dos veces y llega
en 4.

| Instante | Dron 1 | Dron 2 | Dron 3 |
|---|---|---|---|
| 0 | `start` | `start` | `start` |
| 1 | `narrow` | `start` (espera) | `start` (espera) |
| 2 | `goal` | `narrow` | `start` (espera) |
| 3 | — | `goal` | `narrow` |
| 4 | — | — | `goal` |

Y la salida, que omite a los drones que no se mueven:

```
D1-narrow
D1-goal D2-narrow
D2-goal D3-narrow
D3-goal
```

Cuatro turnos, que es el mínimo posible: por `narrow` solo pasa un dron por
turno, y cada uno necesita dos para llegar.

### 5.2 `restricted_chain.txt`: el dron en el aire

Un solo dron, pero dos zonas `restricted` seguidas. `can_move(start, r1, 0)`
calcula coste 2, comprueba la conexión en 0 y en 1 y `r1` en 2. Al grabar, la
conexión `start-r1` queda ocupada dos instantes y ninguna zona lo está en el
instante 1. Lo mismo para `r1 → r2`. El resultado son cinco turnos:

```
D1-start-r1
D1-r1
D1-r1-r2
D1-r2
D1-goal
```

Las líneas 1 y 3 nombran la conexión porque el dron está en el aire. Si otro
dron quisiera usar `start-r1` en el instante 1, `link_has_room` se lo
impediría; si quisiera cruzarla de frente, `would_swap` también, aunque la
capacidad fuera 2.

### 5.3 Una replanificación con un dron en el aire

Supongamos `W = 4`, así que SP08 replanifica en los instantes 0, 2, 4… Un dron
salió en el instante 1 hacia una `restricted`: en el instante 2 sigue en la
conexión y aterriza en 3. SP08 llama a `clear_from(2, keep={ese dron})`.
Todas las reservas desde el instante 2 desaparecen —las de todos los demás
drones, que van a replanificar— salvo las de ese dron, que conserva su
conexión en 2 y su zona en 3. Luego SP07 planifica a los demás, y cualquiera
que quisiera aterrizar en esa misma zona en el instante 3 encuentra la reserva
y busca otra cosa. El dron en el aire no se replanifica: llega donde tenía que
llegar.

Sin `keep`, el caso anterior acabaría con dos drones en una zona de capacidad
1, o con un dron sin sitio donde aterrizar. Ninguna de las dos cosas se puede
arreglar a posteriori, y las dos serían muy difíciles de rastrear desde la
salida.

---

## 6. Lo que este diseño no garantiza

WHCA\* es la aproximación práctica estándar a un problema que, resuelto de forma
óptima, es NP-difícil. El precio es que **no es completo ni óptimo**. El caso
clásico en el que falla es el de dos drones que tienen que cruzarse en sentidos
opuestos por un pasillo de una sola zona, sin apartadero: la regla anti-cruce
de `would_swap` les impide atravesarse, la capacidad les impide coincidir, y
ninguna ventana ofrece una salida si ninguno puede retroceder a un sitio libre.
El test `swap_corridor.txt` de SP07 no tiene un resultado "correcto" fijado de
antemano: su valor es documentar qué hace el algoritmo ahí.

Ese riesgo es la razón de dos decisiones que viven en SP08, fuera de estas dos
piezas: un límite de turnos de seguridad que convierte un posible cuelgue en un
error claro (un programa que se cuelga cuenta como no funcional, Cap. III.1), y
una comprobación inicial con `AbstractDistance.is_reachable` que detecta los
mapas imposibles en el turno 0.

La otra renuncia consciente es de rendimiento. Contar la conexión `restricted`
ocupada durante los dos turnos del tránsito es la lectura literal del subject
(*"the drone occupies the connection during transit"*), pero hay proyectos que
la cuentan solo en el turno de salida. En mapas con enlaces `restricted` de
capacidad 1, la lectura estricta puede costar algún turno frente a esas
implementaciones. Preferimos la regla correcta al número más bajo.

---

## 7. Resumen: quién hace qué

| Pieza | Responsabilidad | Si faltara… |
|---|---|---|
| `zone_has_room` | Respetar `max_drones`; hubs ilimitados sin casos especiales | Los drones no podrían ni esperar en `start_hub` |
| `link_has_room` | Respetar `max_link_capacity` | Varios drones cruzarían un enlace de capacidad 1 a la vez |
| `would_swap` | Impedir cruces de frente | Dos drones se atravesarían en enlaces de capacidad ≥ 2 |
| `can_move` | Una sola pregunta para todo un movimiento, coste 1 o 2 | SP07 olvidaría alguna comprobación en algún mapa |
| `reserve_move` | Grabar un movimiento entero, atómico, con coste deducido | Tablas a medias y costes incoherentes |
| `reserve_wait` | Grabar cada turno de espera | Un dron quieto sería invisible para los demás |
| `_add` | No contar dos veces al mismo dron | Zonas "llenas" con un solo ocupante |
| `clear_from` + `keep` | Tirar predicciones viejas sin abandonar a los drones en el aire | Los drones se esquivarían a sí mismos, o no tendrían dónde aterrizar |
| `ReservationError` | Hacer ruidoso cualquier desacuerdo entre búsqueda y tabla | Colisiones silenciosas lejos de su causa |
| Estado `(zona, turno)` | Convertir otros drones en obstáculos temporales | No habría cooperación |
| Sucesor "esperar" | Permitir ceder el paso | "No hay ruta" en cuanto hay dos drones |
| Ventana `W` + ruta parcial | Acotar la búsqueda y replanificar con información fresca | Búsquedas enormes y reservas que condicionan todo el futuro |
| Grabar antes del siguiente | Que cada dron vea a los anteriores | Todos los drones con la misma ruta |
| Orden de prioridad | Decidir quién se lleva las mejores reservas | Resultado dependiente de un detalle arbitrario |
