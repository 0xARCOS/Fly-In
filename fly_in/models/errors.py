class MapError(Exception):
    """Raíz de todos los errores relacionados con un mapa (E/S o contenido)."""


class MapParseError(MapError):
    """
    Error de parseo de un archivo de mapa.

    Lleva siempre la línea original (número + contenido) y la causa,
    tal como pide el checklist de map_parser.py:
    "Cualquier otro fallo de formato -> excepción con línea y causa
    en el mensaje".
    """

    def __init__(self, line_num: int, line_content: str, reason: str):
        self.line_num = line_num
        self.line_content = line_content
        self.reason = reason
        message = f"Línea {line_num}: '{line_content}' -> {reason}"
        super().__init__(message)


class MapValidationError(MapError):
    """Fallo del archivo en conjunto (falta start_hub, falta end_hub…).

    A diferencia de `MapParseError`, no hay una única línea a la que
    señalar: la comprobación solo puede hacerse tras leer el archivo
    entero (ver "Deuda conocida #2" en docs/build/SP02-parser.md).
    """
