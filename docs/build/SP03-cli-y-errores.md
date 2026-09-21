# SP03 — CLI y manejo de errores ⬜

**Objetivo:** que el programa sea **ejecutable de verdad** por primera vez:
recibe la ruta de un mapa, lo lee, lo parsea, y si algo falla muestra un mensaje
limpio — nunca un traceback.

**Prerequisitos:** [SP02](./SP02-parser.md) verde.

**Criterio de salida:** `make run MAP=maps/valid/linear.txt` imprime un resumen
del grafo; **ningún** input imaginable produce un traceback.

**Por qué ahora y no al final:** porque hasta que no puedas ejecutar el programa
contra un fichero, cada prueba que hagas será desde el intérprete o desde un
test. Media hora aquí te ahorra fricción en los ocho subproyectos siguientes.
Además, el subject es tajante: *"If your program crashes due to unhandled
exceptions during the review, it will be considered non-functional"* *(Cap.
III.1)*.

---

## Paso 1 — Los argumentos de línea de comandos

Usa `argparse` de la librería estándar. Te da `--help` gratis, valida tipos y
produce mensajes de error decentes sin escribirlos tú.

```python
def build_parser() -> argparse.ArgumentParser:
    """Define los argumentos de línea de comandos de Fly-In."""
```

| Argumento | Tipo | Defecto | Para qué |
|---|---|---|---|
| `map_file` | posicional, ruta | — | El mapa a simular |
| `--window W` / `-w` | entero | 8 | Ventana de WHCA\* ([SP07](./SP07-whca.md)) |
| `--no-color` | bandera | falso | Desactiva ANSI ([SP10](./SP10-visualizacion.md)) |
| `--quiet` / `-q` | bandera | falso | Solo el formato de salida, sin visualización |
| `--metrics` | bandera | falso | Métricas secundarias por `stderr` ([SP11](./SP11-benchmarks-y-readme.md)) |

Los tres últimos aún no hacen nada. Declararlos ahora te ahorra volver a tocar
el CLI en cada subproyecto, y `--window` es el que te permitirá comparar
configuraciones en SP11 sin editar código.

⚠️ **No lo des por sentado — usa `type=Path`, no `type=str`**
`argparse` acepta `type=pathlib.Path` y te da un objeto `Path` directamente. Con
él, `.read_text()`, `.exists()` y `.is_file()` son métodos, no funciones de
`os.path` mal recordadas. Y `mypy` puede verificar que no mezclas rutas con
cadenas cualesquiera.

## Paso 2 — Leer el fichero, con todo lo que puede salir mal

```python
def read_map_file(path: Path) -> str:
    """Lee un archivo de mapa y devuelve su contenido.

    Raises:
        MapError: si el archivo no existe, no se puede leer o no es texto.
    """
```

Los cuatro fallos reales que tienes que cubrir:

| Qué pasa | Excepción de Python | Mensaje que debe ver el usuario |
|---|---|---|
| El archivo no existe | `FileNotFoundError` | `No existe el archivo de mapa: maps/typo.txt` |
| Es un directorio | `IsADirectoryError` | `La ruta no es un archivo: maps/` |
| Sin permiso de lectura | `PermissionError` | `Sin permiso para leer: maps/x.txt` |
| No es texto UTF-8 (un `.png`, un binario) | `UnicodeDecodeError` | `El archivo no es texto legible: foto.png` |

⚠️ **No lo des por sentado — `UnicodeDecodeError` es el que todo el mundo olvida**
Los tres primeros son evidentes. El cuarto salta cuando alguien pasa un binario
por error, y como `UnicodeDecodeError` hereda de `ValueError` y no de `OSError`,
un `except OSError` no lo captura. Pruébalo: `make run MAP=docs/Fly-In.pdf`.

⚠️ **No lo des por sentado — usa un context manager (o `Path.read_text`)**
El subject lo pide explícitamente: *"Prefer context managers for resources like
files (…) to ensure automatic cleanup"* *(Cap. III.1)*. `path.read_text(encoding="utf-8")`
ya lo hace internamente y es la forma más corta de cumplirlo.

## Paso 3 — La frontera de excepciones

**La regla:** las excepciones viajan hacia arriba sin capturarse hasta `main()`,
y ahí —y solo ahí— se convierten en un mensaje y un código de salida.

```python
def main() -> int:
    """Punto de entrada. Devuelve el código de salida del proceso."""
    args = build_parser().parse_args()
    try:
        content = read_map_file(args.map_file)
        nb_drones, graph = MapParser.parse(content)
    except MapError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    ...
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Tres detalles que importan:

- **`main()` devuelve `int`**, y `sys.exit()` lo usa como código de salida del
  proceso. 0 = éxito, distinto de 0 = fallo. Es lo que permite encadenar
  `make run && algo` o comprobarlo desde un test.
- **Los errores van a `stderr`**, nunca a `stdout`. `stdout` está reservado para
  el formato de salida del subject (ver [`03-formato-datos.md`](../03-formato-datos.md)).
- **Se captura la clase raíz `MapError`**, no cada subclase. Por eso conviene
  cerrar antes la [deuda #2 de SP02](./SP02-parser.md#deuda-conocida).

⚠️ **No lo des por sentado — no envuelvas todo en `except Exception`**
Es tentador poner un `except Exception` gigante en `main()` para que "nunca
crashee". No lo hagas: esconderá tus propios bugs (un `AttributeError` por un
typo se mostrará como "Error: 'NoneType' object has no attribute 'name'" y
seguirás sin saber dónde está). Captura las excepciones que **esperas**
—`MapError`, y en SP08 `SimulationError`— y deja que un bug de programación se
manifieste como el bug que es, durante el desarrollo.

Sí hay una excepción que conviene capturar aparte: `KeyboardInterrupt`, para que
un Ctrl+C durante un mapa grande salga limpio en vez de con un traceback feo.

## Paso 4 — Un resumen del grafo, para ver que funciona

Mientras no exista el simulador, que `main()` imprima un resumen legible:

```console
$ make run MAP=maps/valid/bottleneck.txt
Mapa: maps/valid/bottleneck.txt
Drones: 3
Zonas: 3 (start_hub=start, end_hub=goal)
Conexiones: 2
  start -> narrow  [cap=1]
  narrow -> goal   [cap=1]
```

Es desechable —lo sustituye la salida real en SP09— pero durante seis
subproyectos va a ser tu forma de comprobar que un mapa se lee como esperas.

## Paso 5 — El `Makefile` con parámetro

```makefile
MAP ?= maps/valid/linear.txt

run:
	$(PYTHON) -m fly_in.main $(MAP)

debug:
	$(PYTHON) -m pdb -m fly_in.main $(MAP)
```

`?=` asigna solo si la variable no viene ya del entorno, así que
`make run MAP=otro.txt` la sobrescribe y `make run` a secas usa el mapa por
defecto. Es la forma estándar de parametrizar un target.

---

## Tests de cierre (`test/test_cli.py`)

- [ ] Fichero inexistente → código de salida 1 y mensaje en `stderr` que contiene la ruta
- [ ] Directorio en vez de fichero → error limpio
- [ ] Fichero binario (usa `docs/Fly-In.pdf`) → error limpio, no `UnicodeDecodeError`
- [ ] Mapa vacío → error limpio
- [ ] Mapa de `maps/errors/` → mensaje con el número de línea
- [ ] Mapa válido → código de salida 0
- [ ] **Ninguno de los anteriores imprime la palabra `Traceback`**

El último es el que de verdad verifica el criterio del subject. Captúralo con
`capsys` de pytest o ejecutando el módulo con `subprocess`.

---

## Criterio de salida

- [ ] `make run` funciona con y sin `MAP=`
- [ ] Los seis casos de error dan mensaje limpio y código ≠ 0
- [ ] `--help` explica cada argumento
- [ ] Mensajes de error en un solo idioma y con la ruta/línea del problema
- [ ] `make lint-strict` pasa

## Decisiones a anotar

- ¿Idioma de los mensajes al usuario? *(El `README.md` debe ser inglés
  obligatoriamente; los mensajes del programa no lo especifica el subject —
  elige uno y sé consistente.)*
- ¿Códigos de salida distintos según el tipo de error, o siempre 1?
- ¿El resumen del grafo se queda como modo `--dry-run` o se elimina en SP09?
