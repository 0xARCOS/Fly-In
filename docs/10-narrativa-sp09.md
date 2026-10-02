# SP09 contado de principio a fin

Continúa [`09-narrativa-sp08.md`](./09-narrativa-sp08.md). El simulador ya
sabía mover a todos los drones sin romper ninguna regla y devolvía una
**traza**: una lista de `Move` por turno. Este documento cuenta el último paso
antes de que alguien de fuera pueda juzgar el programa: convertir esa traza en
el texto exacto que pide el subject. Es el subproyecto más corto y, a la vez,
el único cuyo resultado se compara **carácter a carácter**.

> **Estado.** Implementado en
> [`fly_in/output/formatter.py`](../fly_in/output/formatter.py), cableado en
> [`fly_in/main.py`](../fly_in/main.py) y cubierto por
> [`test/test_output_format.py`](../test/test_output_format.py). La guía de
> pasos es [`SP09-formato-salida.md`](./build/SP09-formato-salida.md).

---

## 1. El problema: la única parte que se lee con lupa

Todo lo anterior se evalúa por sus efectos: si el algoritmo es bueno, salen
pocos turnos. La salida, en cambio, se evalúa por su **forma**. El Cap. VII.5
fija cinco reglas, y basta con romper una para que un evaluador (o su script)
no pueda contar tus turnos:

1. Una línea por turno.
2. Los movimientos del turno, separados por espacios.
3. Cada uno, `D<id>-<zona>`, o `D<id>-<conexión>` si el dron sigue en vuelo
   hacia una `restricted`.
4. Los drones que no se mueven no aparecen.
5. Los entregados no vuelven a aparecer.

Y hay una sexta regla que no está escrita pero que manda sobre las demás:
**en `stdout` no puede haber nada más**. Si el número de turnos es la nota, y
el evaluador lo cuenta con `wc -l`, cualquier línea de más es un turno que no
existió.

---

## 2. Lo que SP08 dejó preparado

El simulador no devuelve estados: devuelve **lo que pasó**. Cada `Move` lleva
el dron, el origen, el destino, la conexión y un booleano, `arrives`:

| `arrives` | Qué significa | Qué se imprime |
|---|---|---|
| `True` | El dron acaba el turno en `target` | `D<id>-<target>` |
| `False` | El dron acaba el turno en el aire, sobre `connection` | `D<id>-<connection>` |

Con eso, `format_move` es una sola línea de lógica. La guía proponía otra
firma, `format_move(drone, step)`, que decidía mirando `drone.state`. Se
descartó por un motivo sutil: cuando el formateador se ejecuta, el turno ya se
ha aplicado, y `drone.state` describe el *después*. Un dron que aterriza en
una `restricted` estaba `IN_TRANSIT` antes del turno y `MOVING` después;
según en qué momento se pregunte, se imprimiría la conexión o la zona. El
`Move` no tiene ese problema: es un hecho, no un estado.

---

## 3. Las tres funciones

**`format_move(move)`** devuelve `D1-roof1` o `D1-hub-roof1`. El nombre de la
conexión es `Connection.name`, que es `<zona_a>-<zona_b>` en el orden del
archivo. Un dron que la recorre al revés imprime **el mismo nombre**: el
subject dice *"the name of the connection"*, no un nombre orientado. Hay un
test que recorre una conexión en sentido contrario para fijarlo.

**`format_turn(moves)`** ordena por id y une con un espacio. El simulador ya
devuelve los `Move` ordenados, pero el formateador vuelve a ordenarlos: el
formato no debe depender de un detalle interno de otro módulo.

**`format_trace(trace)`** aplica lo anterior a cada turno y **descarta los
turnos sin movimientos**. ¿Es legal quitar un turno? Solo si el mundo antes y
después de él es idéntico. Lo es: si nadie se ha movido, nadie estaba en el
aire (quien está en el aire aterriza obligatoriamente en su segundo turno, y
eso es un movimiento), así que todos siguen donde estaban y los turnos
siguientes son igual de legales un turno antes. En la práctica, el simulador
no produce ninguno en los 19 mapas; la regla existe para que la cuenta de
líneas y la de turnos no puedan divergir nunca.

---

## 4. `stdout` es sagrado

`main.py` imprime las líneas de turno en `stdout` **después** de la
simulación y de la animación, y nada más. La visualización (SP10), el resumen,
las métricas (`--metrics`) y los errores van a `stderr`, y la animación, a la
ventana.

Hubo un último intruso que no estaba en el código Python: `make`. Una regla de
`Makefile` imprime el comando que ejecuta **por `stdout`**, así que
`make run > salida.txt` metía `.venv/bin/python -m fly_in.main …` como primera
línea. Se detectó al comprobar lo que el `README.md` promete (que `wc -l` da
los turnos) y se arregló con un `@` delante del comando.

```console
$ make run MAP=maps/valid/bottleneck.txt > out.txt    # la animación se ve igual
$ cat out.txt
D1-narrow
D1-goal D2-narrow
D2-goal D3-narrow
D3-goal
$ wc -l < out.txt
4
```

---

## 5. Todo junto

`restricted_chain.txt` es el caso que más enseña, porque un único dron genera
dos líneas por cada zona `restricted`:

```
D1-start-r1      ← turno 1: entra en la conexión, sigue en el aire
D1-r1            ← turno 2: aterriza
D1-r1-r2
D1-r2
D1-goal
```

Cinco líneas para tres zonas: 2 + 2 + 1. Si el formateador imprimiera solo las
llegadas, saldrían tres líneas y la cuenta de turnos sería falsa.

---

## 6. Cómo sabemos que funciona

- Casos exactos: un movimiento, un tránsito en sus dos turnos, una conexión
  recorrida al revés, dos drones con un solo espacio, orden por id con
  `D10` después de `D2`, turno vacío.
- Salidas escritas a mano para `linear.txt` y `bottleneck.txt`.
- En los 19 mapas: cada línea cumple `^D\d+-\S+( D\d+-\S+)*$`, no contiene
  ningún código ANSI, hay tantas líneas como turnos, y ningún dron entregado
  reaparece.
- En la CLI: `stdout` contiene exactamente las líneas de turno **incluso con
  la visualización activa**, y `stderr` recibe el resto.

---

## 7. Resumen: quién hace qué

| Pieza | Responsabilidad | Regla del subject |
|---|---|---|
| `Move.arrives` (SP08) | Decir si el dron acaba el turno en la zona o en la conexión | Cap. VII.5 (formato en tránsito) |
| `format_move` | `D<id>-<zona>` / `D<id>-<conexión>`, nombre sin orientar | Cap. VII.5 |
| `format_turn` | Orden por id, un espacio | Cap. VII.5 |
| `format_trace` | Una línea por turno; sin líneas vacías | Cap. VII.5 y VII.6 (la métrica) |
| `main.py` + `Makefile` | `stdout` solo con líneas de turno; todo lo demás a `stderr` | Cap. VII.5 |

Continúa en [`11-narrativa-sp10.md`](./11-narrativa-sp10.md): cómo se ve todo
esto en pantalla.
