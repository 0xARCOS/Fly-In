"""Excepciones de lectura y validación de mapas."""


class MapError(Exception):
    """Raíz de todos los errores relacionados con un mapa (E/S o contenido)."""


class MapParseError(MapError):
    """Error de parseo en una línea concreta del archivo de mapa.

    Lleva siempre la línea original (número + contenido) y la causa, como
    exige el Cap. VII.4: "a clear error message indicating the line and
    cause".
    """

    def __init__(self, line_num: int, line_content: str, reason: str) -> None:
        """Crea el error.

        Args:
            line_num: Número de línea en el archivo original (1-based).
            line_content: Texto de la línea, ya sin comentario.
            reason: Causa del fallo.
        """
        self.line_num = line_num
        self.line_content = line_content
        self.reason = reason
        super().__init__(f"Line {line_num}: '{line_content}' -> {reason}")


class MapValidationError(MapError):
    """Fallo del archivo en conjunto (vacío, falta start_hub, sin ruta…).

    A diferencia de `MapParseError`, no hay una única línea a la que
    señalar: la comprobación solo puede hacerse tras leer el archivo entero.
    """
