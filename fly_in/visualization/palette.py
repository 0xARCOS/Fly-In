"""Colors: from the map's `color=` to ANSI codes (SP10).

The subject does not fix the list of colors (Chap. VI): any word is valid.
That is why there are three levels:

1. Known names → RGB from a table.
2. `rainbow` → a hue that rotates with each frame.
3. Anything else → a vivid hue derived from the name, stable across runs.
   Never an exception because of a decorative metadata value.
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

# Okabe-Ito palette without black (invisible on a dark background): D1-D7.
OKABE_ITO_COLORS: Tuple[RGB, ...] = (
    (86, 180, 233),   # D1: sky blue
    (0, 158, 115),    # D2: bluish green
    (213, 94, 0),     # D3: vermillion
    (204, 121, 167),  # D4: reddish purple
    (0, 114, 178),    # D5: blue
    (240, 228, 66),   # D6: yellow
    (230, 159, 0),    # D7: orange
)

# The standard 16-color xterm palette, for terminals without truecolor.
_BASIC: Tuple[Tuple[int, RGB], ...] = (
    (30, (0, 0, 0)), (31, (205, 0, 0)), (32, (0, 205, 0)),
    (33, (205, 205, 0)), (34, (0, 0, 238)), (35, (205, 0, 205)),
    (36, (0, 205, 205)), (37, (229, 229, 229)), (90, (127, 127, 127)),
    (91, (255, 0, 0)), (92, (0, 255, 0)), (93, (255, 255, 0)),
    (94, (92, 92, 255)), (95, (255, 0, 255)), (96, (0, 255, 255)),
    (97, (255, 255, 255)),
)

# Interface colors (they do not come from the map).
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
    """From color names (from the map or the interface) to RGB."""

    @staticmethod
    def hue(value: float, saturation: float = 0.85,
            bright: float = 1.0) -> RGB:
        """Color of hue `value` (0..1)."""
        r, g, b = colorsys.hsv_to_rgb(value % 1.0, saturation, bright)
        return int(r * 255), int(g * 255), int(b * 255)

    @staticmethod
    def resolve(name: Optional[str], frame: int = 0) -> Optional[RGB]:
        """RGB of a zone's `color=`, or None if it has none.

        It never fails: an unknown name gets a hue derived from its hash.
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
        """A vivid, distinct hue per drone.

        D1 to D7: Okabe-Ito palette (color-blind friendly).
        From D8 on: golden angle between neighbors.
        """
        if 1 <= drone_id <= len(OKABE_ITO_COLORS):
            return OKABE_ITO_COLORS[drone_id - 1]
        return Palette.hue((drone_id - 8) * 0.61803398875, saturation=0.65)


class Painter:
    """Apply ANSI styles, or nothing if color is disabled.

    It is the only place that writes escape codes, and it always closes
    with RESET: the color never sticks to the user's prompt.
    """

    def __init__(self, enabled: bool, truecolor: bool = True) -> None:
        """`enabled=False` produces plain text (NO_COLOR, pipes)."""
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
        """`text` with the requested style."""
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
        """Does the terminal understand 24-bit RGB colors?"""
        return os.environ.get("COLORTERM", "").lower() in (
            "truecolor", "24bit"
        )

    @staticmethod
    def strip_ansi(text: str) -> str:
        """The text without ANSI codes."""
        return _ANSI.sub("", text)

    @staticmethod
    def visible_len(text: str) -> int:
        """On-screen length: not counting the ANSI codes."""
        return len(Painter.strip_ansi(text))

    @staticmethod
    def pad(text: str, width: int) -> str:
        """Pad with spaces up to `width` visible columns."""
        return text + " " * max(0, width - Painter.visible_len(text))

    def _color(self, rgb: RGB, background: bool) -> str:
        """Color code: direct RGB or the nearest of 16."""
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
