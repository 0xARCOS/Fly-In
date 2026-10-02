# SP02 — Parser

> **Estado:** implementado en
> [`fly_in/parsing/map_parser.py`](../../fly_in/parsing/map_parser.py) y
> probado en [`test/test_parser.py`](../../test/test_parser.py) (86 tests).
> Los 9 mapas de `maps/valid/` y los 10 oficiales parsean; los 10 de
> `maps/errors/` fallan con su causa.

## El problema

El subject describe el formato del mapa (Cap. VI) y exige que cualquier error
pare el programa con *"a clear error message indicating the line and cause"*
(Cap. VII.4). Un error en la línea 5 del editor tiene que decir "línea 5", aunque
haya comentarios y líneas vacías antes.

## La decisión: piezas pequeñas y un único punto que añade la línea

`MapParser` es una clase con métodos estáticos; cada uno resuelve una parte y
lanza `ValueError` con la causa:

| Método | Entrada → salida |
|---|---|
| `clean_lines(texto)` | `[(nº de línea original, texto sin comentario)]`, sin líneas vacías |
| `parse_metadata("[k=v …]", claves_permitidas)` | `{"k": "v"}`; rechaza tokens sin `=`, vacíos, repetidos o claves no permitidas |
| `parse_positive_int(valor, campo)` | Entero > 0 o `ValueError` |
| `parse_zone_type(valor)` | `ZoneType`, o error con los cuatro válidos |
| `parse_zone_line(línea)` | `(rol, nombre, x, y, metadatos)` |
| `parse_connection_line(línea)` | `(origen, destino, metadatos)` |
| `parse(texto)` | `(nb_drones, Graph)` |

`parse` es el único sitio que conoce el número de línea:

```python
for num_line, content in cleaned[1:]:
    try:
        MapParser._parse_line(content, graph)
    except ValueError as exc:
        raise MapParseError(num_line, content, str(exc))
```

y el mensaje queda así:

```
Error: Line 5: 'hub: mid-zone 1 0' -> Zone name can't contain '-': 'mid-zone'
```

Al terminar, si falta `start_hub` o `end_hub` lanza `MapValidationError`: no
hay una línea a la que señalar.

## Decisiones que hay que saber explicar

1. **El número de línea se toma antes de filtrar.** `clean_lines` enumera las
   líneas del fichero y luego quita comentarios y vacías.
2. **Los metadatos se separan antes de contar campos.** En
   `hub: roof 3 4 [zone=restricted color=red]` se aísla el bloque `[...]` y
   quedan exactamente tres campos: nombre, x, y.
3. **Claves permitidas por tipo de línea.** Zonas: `zone`, `color`,
   `max_drones`. Conexiones: `max_link_capacity`. Una clave de más es un
   error, no se ignora.
4. **`start_hub` y `end_hub` ignoran `max_drones`**, aunque sea inválido
   (Cap. VII.4): su capacidad es `UNLIMITED`. Sí se rechaza que sean
   `blocked`.
5. **Duplicados en cualquier sentido.** `Graph` usa `frozenset({a, b})`, así
   que `a-b` y `b-a` son la misma conexión.
6. **Coordenadas enteras, también negativas.** Solo sirven para dibujar.

## Alternativa descartada: un `parse` monolítico

Con todo dentro de `parse`, cada regla solo se podría probar con un archivo
entero. Separado, cada pieza tiene sus tests y los errores dicen qué parte de
la línea falló.

## Mapas de error

| Mapa | Error |
|---|---|
| `missing_nb_drones.txt` | `MapParseError` en la primera línea |
| `no_start.txt` | `MapValidationError: Map needs a 'start_hub'` |
| `two_starts.txt` | `Only one 'start_hub' is allowed` |
| `duplicate_zone_name.txt` | `Zone name '…' is already defined` |
| `duplicate_connection.txt` | `Duplicate connection between …` |
| `connection_unknown_zone.txt` | `Connection references undefined zone` |
| `dash_in_name.txt` | `Zone name can't contain '-'` |
| `invalid_zone_type.txt` | `Invalid zone type '…'` |
| `malformed_metadata.txt` | `Invalid metadata token` |
| `negative_capacity.txt` | `must be a positive integer` |

`test_error_maps_fail_with_the_right_cause` los recorre todos.

## Verificación

```console
$ python -m fly_in.main maps/errors/negative_capacity.txt
Error: Line 5: 'hub: mid 1 0 [max_drones=-1]' -> max_drones must be a positive integer, got -1
$ python -m fly_in.main maps/errors/no_start.txt
Error: Map needs a 'start_hub'
```

El código de salida es 1 en los dos casos, y no hay traceback.

---

Continúa en [SP03](./SP03-narrativa.md): la línea de comandos y los errores.
