"""Colores: del `color=` del mapa a códigos ANSI (SP10).

El subject no fija la lista de colores (Cap. VI): cualquier palabra vale.
Por eso hay tres niveles:

1. Nombres conocidos → RGB de una tabla.
2. `rainbow` → un tono que gira con cada fotograma.
3. Cualquier otra cosa → un tono vivo derivado del nombre, estable entre
   ejecuciones. Nunca una excepción por un metadato decorativo.
"""

import colorsys
import hashlib
import os
import re
from typing import Dict, Optional, Tuple

RGB = Tuple[int, int, int]

RESET = "\033[0m"
_ANSI = re.compile(r"\033\[[0-9;?]*[A-Za-z]")

NAMED: Dict[str, RGB] = {
    "black": (70, 70, 80), "white": (235, 235, 245),
    "gray": (140, 140, 150), "grey": (140, 140, 150),
    "silver": (192, 192, 200), "red": (255, 70, 70),
    "darkred": (170, 20, 30), "crimson": (220, 20, 60),
    "maroon": (150, 30, 50), "pink": (255, 120, 190),
    "coral": (255, 127, 80), "salmon": (250, 128, 114),
    "orange": (255, 150, 30), "gold": (255, 210, 0),
    "yellow": (255, 240, 60), "olive": (160, 160, 40),
    "lime": (120, 255, 60), "green": (40, 220, 90),
    "darkgreen": (20, 130, 50), "teal": (0, 170, 170),
    "cyan": (40, 230, 255), "turquoise": (64, 224, 208),
    "lightblue": (140, 200, 255), "skyblue": (100, 190, 255),
    "blue": (60, 120, 255), "darkblue": (30, 50, 170),
    "navy": (40, 50, 140), "indigo": (100, 60, 220),
    "purple": (170, 70, 255), "violet": (210, 110, 255),
    "magenta": (255, 60, 220), "brown": (170, 100, 50),
}

# Paleta Okabe-Ito: 8 colores accesibles para daltonismo.
OKABE_ITO_COLORS: Tuple[RGB, ...] = (
    (230, 159, 0),    # 0: Amarillo/Naranja
    (86, 180, 233),   # 1: Azul cielo
    (0, 158, 115),    # 2: Verde azulado
    (213, 94, 0),     # 3: Naranja oscuro
    (204, 121, 167),  # 4: Rosa
    (0, 114, 178),    # 5: Azul
    (240, 228, 66),   # 6: Amarillo
    (230, 97, 0),     # 7: Naranja rojo
)

# La paleta estándar de 16 colores de xterm, para terminales sin truecolor.
_BASIC: Tuple[Tuple[int, RGB], ...] = (
    (30, (0, 0, 0)), (31, (205, 0, 0)), (32, (0, 205, 0)),
    (33, (205, 205, 0)), (34, (0, 0, 238)), (35, (205, 0, 205)),
    (36, (0, 205, 205)), (37, (229, 229, 229)), (90, (127, 127, 127)),
    (91, (255, 0, 0)), (92, (0, 255, 0)), (93, (255, 255, 0)),
    (94, (92, 92, 255)), (95, (255, 0, 255)), (96, (0, 255, 255)),
    (97, (255, 255, 255)),
)

# Colores de la interfaz (no vienen del mapa).
UI_FRAME: RGB = (90, 110, 160)
UI_TITLE: RGB = (0, 255, 200)
UI_ACCENT: RGB = (255, 60, 220)
UI_GOOD: RGB = (60, 255, 120)
UI_WARN: RGB = (255, 190, 40)
UI_HOT: RGB = (255, 70, 70)
UI_DIM: RGB = (110, 115, 135)
UI_TEXT: RGB = (220, 225, 240)
UI_FLIGHT: RGB = (255, 255, 140)


class Palette:
    """De nombres de color (del mapa o de la interfaz) a RGB."""

    @staticmethod
    def hue(value: float, saturation: float = 0.85,
            bright: float = 1.0) -> RGB:
        """Color de tono `value` (0..1)."""
        r, g, b = colorsys.hsv_to_rgb(value % 1.0, saturation, bright)
        return int(r * 255), int(g * 255), int(b * 255)

    @staticmethod
    def resolve(name: Optional[str], frame: int = 0) -> Optional[RGB]:
        """RGB del `color=` de una zona, o None si no tiene.

        Nunca falla: un nombre desconocido obtiene un tono derivado de su
        hash.
        """
        if name is None:
            return None
        key = name.strip().lower()
        if key in NAMED:
            return NAMED[key]
        if key == "rainbow":
            return Palette.hue(frame * 0.07)
        if re.fullmatch(r"#[0-9a-f]{6}", key):
            return int(key[1:3], 16), int(key[3:5], 16), int(key[5:7], 16)
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        return Palette.hue(digest[0] / 256.0)

    @staticmethod
    def drone_color(drone_id: int) -> RGB:
        """Un tono vivo y distinto por dron.

        Primeros 8 drones: paleta Okabe-Ito (accesible a daltonismo).
        Resto: ángulo dorado entre vecinos.
        """
        if drone_id < len(OKABE_ITO_COLORS):
            return OKABE_ITO_COLORS[drone_id]
        return Palette.hue((drone_id - 8) * 0.61803398875, saturation=0.65)


class Painter:
    """Aplica estilos ANSI, o nada si el color está desactivado.

    Es el único sitio que escribe códigos de escape, y siempre cierra con
    RESET: el color nunca se queda pegado al prompt del usuario.
    """

    def __init__(self, enabled: bool, truecolor: bool = True) -> None:
        """`enabled=False` produce texto plano (--no-color, tuberías)."""
        self.enabled = enabled
        self.truecolor = truecolor

    def __call__(
        self,
        text: str,
        fg: Optional[RGB] = None,
        bg: Optional[RGB] = None,
        bold: bool = False,
        dim: bool = False,
    ) -> str:
        """`text` con el estilo pedido."""
        if not self.enabled or not text:
            return text
        codes = []
        if bold:
            codes.append("1")
        if dim:
            codes.append("2")
        if fg is not None:
            codes.append(self._color(fg, background=False))
        if bg is not None:
            codes.append(self._color(bg, background=True))
        if not codes:
            return text
        return f"\033[{';'.join(codes)}m{text}{RESET}"

    @staticmethod
    def supports_truecolor() -> bool:
        """¿La terminal entiende colores RGB de 24 bits?"""
        return os.environ.get("COLORTERM", "").lower() in (
            "truecolor", "24bit"
        )

    @staticmethod
    def strip_ansi(text: str) -> str:
        """El texto sin códigos ANSI."""
        return _ANSI.sub("", text)

    @staticmethod
    def visible_len(text: str) -> int:
        """Longitud en pantalla: sin contar los códigos ANSI."""
        return len(Painter.strip_ansi(text))

    @staticmethod
    def pad(text: str, width: int) -> str:
        """Rellena con espacios hasta `width` columnas visibles."""
        return text + " " * max(0, width - Painter.visible_len(text))

    def _color(self, rgb: RGB, background: bool) -> str:
        """Código de color: RGB directo o el más cercano de 16."""
        if self.truecolor:
            base = 48 if background else 38
            return f"{base};2;{rgb[0]};{rgb[1]};{rgb[2]}"
        code = min(
            _BASIC,
            key=lambda entry: sum(
                (a - b) ** 2 for a, b in zip(entry[1], rgb)
            ),
        )[0]
        return str(code + 10 if background else code)
