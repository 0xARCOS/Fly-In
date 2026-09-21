class MapParseError(Exception):
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
