# Fase visual: la ventana pygame, elemento a elemento

Referencia para la defensa de la visualización. Cada elemento de la ventana
con el método que lo dibuja en
[`fly_in/visualization/pygame_view.py`](../fly_in/visualization/pygame_view.py)
y la regla del subject que hace visible. El recorrido de los datos (simulador
→ grabación → escena → ventana y log) está en
[`diagramas/E.4-render-pipeline.md`](./diagramas/E.4-render-pipeline.md); los
colores, en [`diagramas/E.5-drone-color.md`](./diagramas/E.5-drone-color.md).

## 1. La idea

La ventana **no calcula nada**. Se simula entero primero; `Scene` precalcula
una vez dónde va cada dron en cada turno y qué conexiones se usan; la ventana
solo consulta esas listas 60 veces por segundo. Si la ventana y `stdout` no
coincidieran, el fallo estaría en el simulador.

## 2. El estado de `PygameView`

Lo único que la ventana guarda por su cuenta es decoración y tiempo:

| Atributo | Qué es |
|---|---|
| `_time` | Segundos de reloj: mueve hélices, anillos, estrellas y latidos |
| `_frame` | Último turno dibujado |
| `_paused` | `SPACE`: el progreso de la animación no avanza |
| `_trails` | Las últimas 16 posiciones de cada dron (estela) |
| `_particles`, `_popups` | Chispas y "+1" de las entregas |
| `_pings` | Anillos de replanificación en curso |
| `closed` | El usuario ha cerrado la ventana: el resto de llamadas no hacen nada |

## 3. Un fotograma: `_paint(k, progreso)`

Por capas, de atrás hacia delante, y al final `pygame.display.flip()` (doble
búfer: nunca se ve a medio pintar):

1. fondo precalculado (`_make_background`),
2. estrellas (`_draw_stars`),
3. conexiones (`_draw_links`),
4. zonas (`_draw_zones`),
5. drones (`_draw_drones`),
6. efectos (`_draw_effects`),
7. etiquetas (`_draw_labels`),
8. tarjeta, si la hay (`_draw_briefing` o `_draw_end_card`).

`play_turn(k, segundos)` repite `_paint` con el progreso de 0 a 1 durante
`--delay` segundos. El movimiento usa `_ease`, una curva cúbica que acelera y
frena (`4p³` en la primera mitad). La ocupación de las zonas cambia a mitad de
viaje, cuando el dron "llega".

## 4. Los elementos

| Elemento | Método | Cómo se dibuja | Qué hace visible |
|---|---|---|---|
| Fondo | `_make_background` | Degradado radial de 40 círculos y una rejilla cada 48 px, una sola vez | — |
| Estrellas | `_draw_stars` | 220 puntos con un brillo que oscila cada uno a su ritmo | — |
| Conexión | `_draw_links` | Sombra ancha y línea; más gruesa cuanto mayor `max_link_capacity` (hasta 5) | `max_link_capacity` |
| Conexión hacia `restricted` | `_dashed` | A trazos ámbar | Que entrar ahí cuesta 2 turnos |
| Conexión con `blocked` | `_draw_links` | Línea roja apagada | Que no se puede pasar |
| Flujo de luz | `_draw_links` | Puntos con halo que avanzan en el sentido del viaje, del color del dron | Qué conexión usa cada dron este turno |
| Zona | `_draw_hex_zone` | Hexágono con halo del color de `color=` (o del tipo) | Tipos y colores del mapa (Cap. VI) |
| `restricted` | `_arc_ring` | Anillo ámbar a trazos que gira | Coste 2 |
| `priority` | `_star` | Estrella dorada (si la zona está vacía) | Que se prefiere |
| `blocked` | `_draw_hex_zone` | Relleno rojizo y una cruz roja | Inaccesible |
| Plazas | `_capacity` | Un punto por plaza encima de la zona; con más de 8 plazas, el texto `n/cap` | `max_drones` (Cap. VII.2) |
| Zona llena | `_draw_hex_zone` | Borde rojo y halo rojo que late | **Por qué espera un dron** |
| Hubs | `_draw_hub` | Plataforma redonda con baliza que late; el número es cuántos drones tiene (en `end_hub`, los entregados) | Progreso |
| Dron | `_draw_drone` | Cuadricóptero: cuerpo, cuatro brazos, hélices que giran, número del dron | Dónde está cada uno |
| Varios drones en una zona | `_spot_pixel` | Cada uno en su hueco de un anillo (12 por anillo) | Ocupación real |
| Dron en el aire | `_draw_drone` | Se eleva, crece un poco y proyecta una sombra en la conexión | Los dos turnos de tránsito a `restricted` (Cap. VII.3) |
| Estela | `_draw_trail` | Puntos que se apagan hacia el fondo | De dónde viene |
| Entrega | `_deliveries`, `_draw_effects` | 26 chispas del color del dron y un "+1" que sube; el dron se encoge dentro del objetivo | Cada dron entregado |
| Replanificación | `_draw_effects` | Anillo rosa que se expande desde el centro y el texto "WHCA\* REPLAN" | Cuándo recalcula el algoritmo (Cap. VII.1) |
| Etiquetas | `_draw_labels` | Primero los hubs, en mayúsculas; las que se solaparían no se dibujan | — |
| Briefing | `_draw_briefing` | Tarjeta con el mapa, drones, zonas, conexiones, ventana, PAR y la cuenta atrás 3-2-1-GO | Qué se va a ver |
| Tarjeta final | `_draw_end_card` | `MISSION COMPLETE`, `ALL DRONES DELIVERED` (u `OVER PAR`), los turnos en grande y seis métricas de los movimientos ejecutados | Métricas (Cap. VII.6) |

## 5. Rendimiento

- `Glow` guarda cada halo (color y radio) ya dibujado; se reutiliza en todos
  los fotogramas.
- `Fonts` guarda cada texto ya renderizado (fuente, texto y color): es lo más
  caro de pygame.
- `Scene` tiene todas las posiciones precalculadas.

## 6. Teclas

| Tecla | Efecto |
|---|---|
| `SPACE` | Pausa y reanuda la animación; el log de la terminal espera a la ventana |
| `ESC`, `Q` o cerrar la ventana | La ventana desaparece en el acto (`pygame.quit()`); la partida sigue en la terminal |
| Cualquier tecla en la tarjeta final | La cierra (si no, se cierra sola a los 20 s) |

## 7. Referencias

- Okabe, M. e Ito, K., *Color Universal Design*: la paleta de los siete
  primeros drones.
- Ángulo áureo (0,618 vueltas) para repartir tonos a partir de D8.
- [no-color.org](https://no-color.org): la variable `NO_COLOR`.
- ECMA-48 (códigos de escape ANSI), para la terminal.
- Documentación de [pygame-ce](https://pyga.me/docs/): `pygame.draw`,
  `pygame.display`, `pygame.time.Clock`, `pygame.event`.

## 8. Comprobación rápida

```console
$ make run MAP=maps/oficial_maps/medium/02_circular_loop.txt
```

Pulsa `SPACE` en el turno 5: `loop_a` (D5 y D6) y `loop_b` (D3 y D4) laten en
rojo porque están llenas, y D2 está en el aire sobre la conexión hacia
`exit_point`. El bloque `T05` de la terminal dice lo mismo con palabras.
