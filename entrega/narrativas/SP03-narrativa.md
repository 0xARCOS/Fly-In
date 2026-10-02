# SP03 — Línea de comandos y manejo de errores

> **Estado:** implementado en [`fly_in/main.py`](../../fly_in/main.py) (clase
> `FlyIn`) y probado en [`test/test_cli.py`](../../test/test_cli.py) (17
> tests). Ningún error de usuario produce un traceback.

## El problema

El subject solo pide recibir el mapa y no romperse: *"If your program crashes
due to unhandled exceptions … it will be considered non-functional"*
(Cap. III.1), y los errores de mapa deben decir la línea y la causa
(Cap. VII.4). Hay que distinguir tres situaciones para quien lo use: el
programa ha ido bien, el mapa o la ejecución han fallado, o los argumentos
están mal.

## La decisión: una única frontera de excepciones

`FlyIn.main()` es el **único** sitio que convierte una excepción en un mensaje.
Por debajo, cada capa lanza la suya con contexto:

```python
def main() -> int:
    args = FlyIn.build_parser().parse_args()
    try:
        return FlyIn.run(args)
    except (MapError, SimulationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130
    except BrokenPipeError:
        # stdout y stderr a /dev/null para salir sin otro error
        ...
        return 1
```

| Situación | Mensaje (en `stderr`) | Código |
|---|---|---|
| Todo bien | — | 0 |
| Fichero inexistente | `Error: Map file not found: nada.txt` | 1 |
| Es una carpeta | `Error: Path is a directory, not a file: maps` | 1 |
| Sin permiso o no es UTF-8 | `Error: Permission denied: …` / `Error: File is not valid UTF-8 text: …` | 1 |
| Error de mapa | `Error: Line 5: '…' -> causa` | 1 |
| `end_hub` inalcanzable | `Error: 'e' is unreachable from 's'` | 1 |
| La simulación no converge | `Error: …` con los drones no entregados | 1 |
| Ctrl+C | `Interrupted by user.` | 130 |
| Quien lee `stdout` se va (`\| head`) | — | 1 |
| Argumento inválido | `error: argument -w/--window: must be > 0, got 0` (argparse) | 2 |

## Los argumentos

| Argumento | Tipo | Defecto | Para qué |
|---|---|---|---|
| `map_file` | ruta | — | El mapa |
| `-w`, `--window` | entero > 0 (`FlyIn.positive_int`) | 8 | Ventana de WHCA\* (SP07) |
| `--view` | `auto`, `window`, `log` | `auto` | Qué visualización (SP10) |
| `-d`, `--delay` | real ≥ 0, no `nan` (`FlyIn.non_negative_float`) | según la vista | Segundos por turno |
| `--metrics` | bandera | — | Métricas secundarias en `stderr` (SP11) |
| `-q`, `--quiet` | bandera | — | Sin visualización |

Los tipos propios hacen que argparse rechace `--window 0` o `--delay nan` con
su mensaje de uso y código 2, antes de leer el mapa.

## El guion de `FlyIn.run`

1. `read_map_file`: comprueba que existe, que no es una carpeta, el permiso y
   que es UTF-8; cada fallo es un `MapError` con la causa.
2. `MapParser.parse` (SP02).
3. `AbstractDistance(graph).is_reachable(start_hub)`: si no hay ruta, error
   inmediato en lugar de dejar al simulador dar vueltas hasta su límite.
4. Elegir vista, ritmo y color (`Session.choose_view`, `make_painter`: color
   solo con `stderr` en una terminal y sin la variable `NO_COLOR`).
5. Simular con `ReplayRecorder` como observador (SP08) y enseñar la partida
   (SP10).
6. Imprimir las líneas del subject en `stdout` y, con `--metrics`, las
   métricas en `stderr`.

## Alternativa descartada: capturar en cada capa

Un `try/except` en cada módulo que imprima y salga repartiría la política de
errores por todo el código. Con una sola frontera, cada capa solo lanza su
excepción y `main` decide qué ve el usuario.

## Verificación

```console
$ python -m fly_in.main nada.txt
Error: Map file not found: nada.txt
$ python -m fly_in.main maps/valid/linear.txt -w 0
python -m fly_in.main: error: argument -w/--window: must be > 0, got 0
$ python -m fly_in.main maps/valid/bottleneck.txt -q | head -1
D1-narrow
```

---

Continúa en [SP04](./SP04-narrativa.md): Dijkstra.
