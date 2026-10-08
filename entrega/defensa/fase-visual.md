# Fase visual: la ventana pygame, elemento a elemento

Referencia para la defensa de la visualización. Cada elemento de la ventana
con el método que lo dibuja en
[`fly_in/visualization/pygame_view.py`](../../fly_in/visualization/pygame_view.py)
y la regla del subject que hace visible. El recorrido de los datos (simulador
→ grabación → escena → ventana y log) está en
[`diagramas/E.4-render-pipeline.md`](../diagramas/E.4-render-pipeline.md); los
colores, en [`diagramas/E.5-drone-color.md`](../diagramas/E.5-drone-color.md).

> **Versión actual: vista mínima.** La primera versión de la ventana era un
> "modo misión" con fondo oscuro, hexágonos con halo, cuadricópteros con
> hélices, estelas, chispas, anillos de replanificación, briefing y tarjeta
> final. Se sustituyó por una vista deliberadamente sobria, pensada para
> **comprobar de un vistazo que la partida es correcta**: fondo blanco,
> círculos, líneas y texto. Qué cambió y por qué está en
> [`CAMBIOS.md`](../CAMBIOS.md).

![medium/02, turno 5: loop_a y loop_b llenas, D2 despegando hacia exit_point](../img/window_medium.png)

## 1. La idea

La ventana **no calcula nada**. Se simula entero primero; `Scene` precalcula
una vez dónde va cada dron en cada turno y cuántos drones hay en cada zona;
la ventana solo consulta esas listas 60 veces por segundo. Si la ventana y
`stdout` no coincidieran, el fallo estaría en el simulador.

## 2. El estado de `PygameView`

La ventana no guarda decoración ni partículas: solo tiempo y teclado.

| Atributo | Qué es |
|---|---|
| `_frame` | Último turno dibujado |
| `_paused` | `SPACE`: el progreso de la animación no avanza |
| `_key_pressed` | Se ha pulsado una tecla (cierra el resumen final) |
| `closed` | El usuario ha cerrado la ventana: el resto de llamadas no hacen nada |
| `_proj`, `_radius`, `_drone` | Proyección mapa → píxeles, radio de zona y de dron (se calculan al abrir) |
| `_font`, `_bold` | Las dos fuentes (`dejavusans`, 14 y 16 px) |

## 3. Un fotograma: `_paint(k, progreso, status)`

Por capas, de atrás hacia delante, y al final `pygame.display.flip()` (doble
búfer: nunca se ve a medio pintar):

1. fondo blanco (`screen.fill(WHITE)`),
2. conexiones (`_draw_links`),
3. zonas con su nombre y ocupación (`_draw_zones`),
4. drones (`_draw_drones`),
5. línea de estado arriba (`_draw_status`).

`play_turn(k, segundos)` repite `_paint` con el progreso de 0 a 1 durante
`--delay` segundos. El movimiento usa `_ease`, un *smoothstep*
(`p²·(3 − 2p)`): arranca y frena suave. La ocupación de las zonas cambia a
mitad de viaje (`progress >= 0.5`), cuando el dron "llega".

## 4. Los elementos

| Elemento | Método | Cómo se dibuja | Qué hace visible |
|---|---|---|---|
| Línea de estado | `_draw_status` | Una línea arriba: mapa · `turn k/N` · `delivered d/n` · teclas (o la cuenta atrás, o el resumen final); `PAUSED` en pausa | Progreso de la partida |
| Conexión | `_draw_links` | Línea gris clara; más gruesa cuanto mayor `max_link_capacity` (hasta 5 px) | `max_link_capacity` |
| Conexión con una `restricted` | `_dashed` | A trazos, gris más oscuro | Que entrar ahí cuesta 2 turnos |
| Zona | `_draw_zones` | Círculo pastel (el color mezclado un 62 % con blanco, `PASTEL`) con borde fino gris | Tipos y colores del mapa (Cap. VI) |
| Color de zona | `_zone_color` | `color=` del mapa si lo hay; si no, por tipo: gris `normal`, amarillo `priority`, naranja `restricted`, gris oscuro `blocked`; verde `start_hub`, azul `end_hub` | Tipo de zona |
| `blocked` | `_draw_zones` | Gris oscuro y una cruz | Inaccesible |
| Hubs | `_draw_zones` | Un 30 % más grandes; se dibujan primero para que su nombre gane si se solapa con otro | Origen y destino |
| Nombre y ocupación | `_draw_zones` | Debajo de la zona: `nombre  ocupados/max_drones`; en `end_hub`, los entregados | `max_drones` (Cap. VII.2) |
| Zona llena | `_draw_zones` | Borde rojo de 2 px y etiqueta roja | **Por qué espera un dron** |
| Dron | `_draw_drone` | Punto de color vivo con borde oscuro y su número en blanco | Dónde está cada uno |
| Color de dron | `_on_white` | El color de `Palette.drone_color`, oscurecido si es muy claro (amarillo) para que se lea sobre blanco | Distinguir drones |
| Varios drones en una zona | `_spot_pixel` | Cada uno en su hueco de un anillo alrededor de la zona (12 por anillo) | Ocupación real |
| Dron en el aire | `_draw_drones` | Se queda en el punto medio de la conexión (a trazos) durante sus dos turnos | El tránsito a `restricted` (Cap. VII.3) |
| Entrega | `_draw_drones` | El dron se encoge dentro del objetivo en el último 30 % del viaje | Cada dron entregado |
| Etiquetas solapadas | `_draw_zones` | Una etiqueta que pisaría otra ya escrita no se dibuja | — |

Por qué así: el dron es un punto **saturado con borde oscuro** y la zona un
círculo **pastel con borde fino**. Aunque tengan el mismo tono, nunca se
confunden, y el número del dron se lee siempre.

## 5. Inicio y final

- **Cuenta atrás** (`countdown`): el mapa en el turno 0 con `starting in 3`,
  `2`, `1` y `GO` en la línea de estado, a la vez que el log de la terminal.
- **Final** (`finish`): la línea de estado dice
  `done in N turns (target T) · press any key to close` hasta que se pulsa una
  tecla o pasan 20 s (`END_HOLD`). Las métricas detalladas las escribe el log
  de la terminal (`MISSION COMPLETE`).

![Último fotograma: 15 turnos contra un objetivo de 15](../img/window_complete.png)

## 6. Rendimiento

- `Scene` tiene todas las posiciones y ocupaciones precalculadas.
- No hay cachés de texto ni de halos: con fondo liso, círculos y una sola
  fuente pequeña, el fotograma completo se dibuja de sobra a 60 fps, también
  en el challenger (25 drones, más de 40 zonas).

## 7. Teclas

| Tecla | Efecto |
|---|---|
| `SPACE` | Pausa y reanuda la animación; el log de la terminal espera a la ventana |
| `ESC`, `Q` o cerrar la ventana | La ventana desaparece en el acto (`pygame.quit()`); la partida sigue en la terminal |
| Cualquier tecla al final | Cierra la ventana (si no, se cierra sola a los 20 s) |

## 8. Referencias

- Okabe, M. e Ito, K., *Color Universal Design*: la paleta de los siete
  primeros drones.
- Ángulo áureo (0,618 vueltas) para repartir tonos a partir de D8.
- Luminancia relativa (coeficientes 0,2126 / 0,7152 / 0,0722, sRGB): decide
  qué colores de dron se oscurecen sobre blanco.
- [no-color.org](https://no-color.org): la variable `NO_COLOR`.
- ECMA-48 (códigos de escape ANSI), para la terminal.
- Documentación de [pygame-ce](https://pyga.me/docs/): `pygame.draw`,
  `pygame.display`, `pygame.time.Clock`, `pygame.event`.

## 9. Comprobación rápida

```console
$ make run MAP=maps/oficial_maps/medium/02_circular_loop.txt
```

Pulsa `SPACE` en el turno 5: `loop_a` (D5 y D6) y `loop_b` (D3 y D4) tienen
el borde y la etiqueta en rojo porque están llenas (`2/2`), y D2 queda en el
aire sobre la conexión a trazos hacia `exit_point`, una `restricted`. El
bloque `T05` de la terminal dice lo mismo con palabras.
