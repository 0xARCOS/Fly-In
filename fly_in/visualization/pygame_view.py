"""La ventana gráfica: la partida animada con pygame (SP10).

La simulación ya ha terminado cuando se abre la ventana: `Scene` tiene
todos los fotogramas. La ventana solo **interpola** entre el fotograma de un
turno y el del siguiente, durante el tiempo que le pide `Session`, mientras
la terminal escribe el log de ese mismo turno. No calcula nada del
algoritmo.

Todo se dibuja con primitivas de `pygame.draw` (líneas, polígonos, círculos
y arcos) y texto: no hay imágenes ni ficheros externos.

Importante: pygame escribe un saludo en **stdout** al importarse. `Session`
define `PYGAME_HIDE_SUPPORT_PROMPT` antes de importar este módulo, porque
stdout es solo para las líneas del subject.
"""

import math
import random
import time
from collections import deque
from dataclasses import dataclass
from types import TracebackType
from typing import (
    Callable,
    Deque,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
)

import pygame

from fly_in.models.zone import UNLIMITED, Zone, ZoneType
from fly_in.simulation.metrics import Metrics
from fly_in.visualization.palette import RGB, Palette
from fly_in.visualization.scene import MapPoint, Scene, Spot

Pixel = Tuple[float, float]

FPS = 60
DEFAULT_SIZE = (1280, 800)
MIN_SIZE = (900, 600)
# Márgenes alrededor del mapa (arriba se escribe el aviso de replan).
TOP, BOTTOM, SIDE = 30, 30, 70
MAX_SCALE = 170.0      # píxeles por unidad del mapa, como mucho
MAX_STRETCH = 2.5      # cuánto puede estirarse un eje respecto al otro
TRAIL = 16             # puntos de estela por dron

# Colores de la interfaz.
BACKGROUND: RGB = (4, 6, 16)
BACKGROUND_GLOW: RGB = (18, 26, 70)
PANEL: RGB = (12, 16, 36)
EDGE: RGB = (64, 80, 160)
TEXT: RGB = (230, 234, 255)
DIM: RGB = (125, 133, 170)
CYAN: RGB = (0, 255, 208)
PINK: RGB = (255, 60, 220)
GOOD: RGB = (60, 255, 120)
WARN: RGB = (255, 190, 40)
HOT: RGB = (255, 77, 94)
FLIGHT: RGB = (255, 255, 140)
GOLD: RGB = (255, 216, 74)
LINK: RGB = (80, 100, 210)
LINK_SHADOW: RGB = (20, 26, 60)
ZONE_FILL: RGB = (24, 30, 70)

# Color de cada tipo de zona si el mapa no trae `color=`.
TYPE_COLOR: Dict[ZoneType, RGB] = {
    ZoneType.NORMAL: (154, 164, 208),
    ZoneType.PRIORITY: GOLD,
    ZoneType.RESTRICTED: (255, 157, 46),
    ZoneType.BLOCKED: HOT,
}


class Projection:
    """Del plano del mapa (y hacia arriba) a píxeles (y hacia abajo).

    Cada eje tiene su escala para aprovechar la ventana, pero ninguno se
    estira más de `MAX_STRETCH` veces el otro: el mapa se sigue
    reconociendo.
    """

    def __init__(self, points: Sequence[MapPoint], size: Tuple[int, int]):
        """Encaja `points` en una ventana de `size` píxeles."""
        width, height = size
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        self.min_x, self.max_y = min(xs), max(ys)
        span_x, span_y = max(xs) - self.min_x, self.max_y - min(ys)
        area_w, area_h = width - 2 * SIDE, height - TOP - BOTTOM
        fit_x = area_w / span_x if span_x else math.inf
        fit_y = area_h / span_y if span_y else math.inf
        base = min(fit_x, fit_y, MAX_SCALE)
        self.scale_x = min(fit_x, base * MAX_STRETCH, MAX_SCALE)
        self.scale_y = min(fit_y, base * MAX_STRETCH, MAX_SCALE)
        self.origin_x = SIDE + (area_w - span_x * self.scale_x) / 2
        self.origin_y = TOP + (area_h - span_y * self.scale_y) / 2
        # Radio de una zona: grande si hay sitio, pequeño si están juntas.
        spacing = min(self.scale_x if span_x else MAX_SCALE,
                      self.scale_y if span_y else MAX_SCALE)
        self.radius = max(9.0, min(24.0, spacing * 0.3))

    def point(self, point: MapPoint) -> Pixel:
        """El píxel de un punto del mapa."""
        return (self.origin_x + (point[0] - self.min_x) * self.scale_x,
                self.origin_y + (self.max_y - point[1]) * self.scale_y)


class Glow:
    """Halos de luz precalculados, que se suman al fondo (BLEND_ADD)."""

    def __init__(self) -> None:
        """Caché vacía: un halo por color y radio."""
        self._cache: Dict[Tuple[RGB, int], pygame.Surface] = {}

    def draw(self, screen: pygame.Surface, color: RGB, center: Pixel,
             radius: float) -> None:
        """Suma un halo de `color` centrado en `center`."""
        size = max(2, int(radius))
        key = (color, size)
        halo = self._cache.get(key)
        if halo is None:
            halo = self._make(color, size)
            self._cache[key] = halo
        screen.blit(halo, (center[0] - size, center[1] - size),
                    special_flags=pygame.BLEND_RGB_ADD)

    @staticmethod
    def _make(color: RGB, radius: int) -> pygame.Surface:
        """Círculos concéntricos: más brillantes cuanto más al centro."""
        halo = pygame.Surface((radius * 2, radius * 2))
        steps = 28
        for step in range(steps):
            strength = ((step + 1) / steps) ** 2.2 * 0.45
            ring = radius * (1 - step / steps)
            shade = (int(color[0] * strength), int(color[1] * strength),
                     int(color[2] * strength))
            pygame.draw.circle(halo, shade, (radius, radius), max(1, ring))
        return halo


class Fonts:
    """Las tipografías de la ventana y una caché de textos ya dibujados."""

    NAMES = ("jetbrainsmono,firacode,dejavusansmono,liberationmono,"
             "consolas,menlo,monospace")

    def __init__(self) -> None:
        """Carga los tamaños que usa la interfaz."""
        self.tiny = pygame.font.SysFont(self.NAMES, 11)
        self.small = pygame.font.SysFont(self.NAMES, 13)
        self.body = pygame.font.SysFont(self.NAMES, 16)
        self.strong = pygame.font.SysFont(self.NAMES, 18, bold=True)
        self.title = pygame.font.SysFont(self.NAMES, 30, bold=True)
        self.big = pygame.font.SysFont(self.NAMES, 48, bold=True)
        self.huge = pygame.font.SysFont(self.NAMES, 120, bold=True)
        self._cache: Dict[Tuple[int, str, RGB], pygame.Surface] = {}

    def render(self, font: pygame.font.Font, text: str,
               color: RGB) -> pygame.Surface:
        """El texto dibujado (se reutiliza si ya se dibujó igual)."""
        key = (id(font), text, color)
        surface = self._cache.get(key)
        if surface is None:
            surface = font.render(text, True, color)
            self._cache[key] = surface
        return surface


@dataclass
class Particle:
    """Una chispa de una entrega: se mueve, se frena y se apaga."""

    x: float
    y: float
    vx: float
    vy: float
    color: RGB
    life: float = 1.0


class PygameView:
    """La ventana: abrirla, animar cada turno, cerrar con la tarjeta final.

    Es un context manager: al salir del `with` se cierra pygame aunque haya
    un error o Ctrl+C. Si el usuario cierra la ventana a mitad, `closed`
    pasa a True y el resto de llamadas no hacen nada: la terminal sigue.
    """

    def __init__(self, scene: Scene, title: str, window: int,
                 target: Optional[int] = None) -> None:
        """Prepara la ventana (sin abrirla todavía)."""
        self.scene = scene
        self.title = title
        self.window = window
        self.target = target
        self.closed = False
        self._screen: Optional[pygame.Surface] = None
        self._clock: Optional[pygame.time.Clock] = None
        self._time = 0.0          # segundos de reloj: animaciones sueltas
        self._frame = 0           # último fotograma completado
        self._paused = False
        self._key_pressed = False
        self._particles: List[Particle] = []
        self._pings: List[float] = []
        self._popups: List[List[float]] = []
        self._trails: Dict[int, Deque[Pixel]] = {
            drone: deque(maxlen=TRAIL) for drone in scene.ids
        }
        self._rng = random.Random(42)

    # --- ciclo de vida -------------------------------------------------

    def __enter__(self) -> "PygameView":
        """La ventana, para usarla dentro del `with`."""
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Cierra pygame pase lo que pase."""
        self.close()

    def open(self) -> bool:
        """Abre la ventana. False si no se puede.

        pygame falla con `pygame.error` si no hay vídeo, y con
        `NotImplementedError` si le falta un módulo (p. ej. las fuentes en
        una instalación incompleta). En los dos casos la partida sigue en
        la terminal.
        """
        try:
            pygame.init()
            info = pygame.display.Info()
            width, height = DEFAULT_SIZE
            if info.current_w > 0 and info.current_h > 0:
                width = min(width, int(info.current_w * 0.92))
                height = min(height, int(info.current_h * 0.88))
            size = (max(width, MIN_SIZE[0]), max(height, MIN_SIZE[1]))
            self._screen = pygame.display.set_mode(size)
            pygame.display.set_caption(f"Fly-In · {self.title}")
            self._fonts = Fonts()
        except (pygame.error, NotImplementedError):
            self.close()
            return False
        self._clock = pygame.time.Clock()
        self._glow = Glow()
        self._proj = Projection(list(self.scene.points.values()), size)
        self._radius = self._proj.radius
        self._drone = max(4.0, self._radius * 0.42)
        self._background = self._make_background(size)
        self._stars = [
            (self._rng.random() * size[0], self._rng.random() * size[1],
             0.3 + self._rng.random() * 0.7, self._rng.random() * 6.3)
            for _ in range(220)
        ]
        return True

    def close(self) -> None:
        """Cierra la ventana y pygame (se puede llamar varias veces)."""
        self._screen = None
        if pygame.get_init():
            pygame.quit()

    # --- lo que pide Session -------------------------------------------

    def countdown(self, value: str, seconds: float) -> None:
        """Enseña el briefing con `value` (3, 2, 1, GO) durante `seconds`."""
        self._animate(seconds, lambda p: self._paint(
            0, 1.0, lambda: self._draw_briefing(value, p)))

    def show_frame(self, turn: int) -> None:
        """Muestra el fotograma `turn` estático (sin animar)."""
        if self.closed:
            return
        # Limpiar estado transitorio al saltar entre fotogramas.
        if turn != self._frame and abs(turn - self._frame) > 1:
            self._clear_transient_state()
        self._paint(turn, 1.0)
        self._frame = turn

    def _clear_transient_state(self) -> None:
        """Vacía estado temporal: partículas, popups, pings."""
        self._particles.clear()
        self._popups.clear()
        self._pings.clear()

    def play_turn(self, turn: int, seconds: float) -> None:
        """Anima del fotograma `turn - 1` al `turn` en `seconds`."""
        if self.closed:
            return
        if turn in self.scene.replan_turns:
            self._pings.append(1.0)
        burst = [False]

        def paint(progress: float) -> None:
            """Un fotograma; las entregas estallan al 60 % del viaje."""
            if progress >= 0.6 and not burst[0]:
                burst[0] = True
                self._deliveries(turn)
            self._paint(turn, progress)

        self._animate(seconds, paint)
        self._frame = turn

    def finish(self, metrics: Metrics, hold: float) -> None:
        """Tarjeta final hasta que se pulse una tecla o pasen `hold` s."""
        if self.closed or hold <= 0:
            return
        self._key_pressed = False
        started = time.perf_counter()
        while not self.closed and not self._key_pressed:
            if time.perf_counter() - started >= hold:
                return
            self._tick()
            self._paint(self._frame, 1.0,
                        lambda: self._draw_end_card(metrics))

    def save_screenshot(self, path: str) -> None:
        """Guarda lo que hay ahora en la ventana (para la documentación)."""
        if self._screen is not None:
            pygame.image.save(self._screen, path)

    # --- tiempo y eventos ----------------------------------------------

    def _animate(self, seconds: float, paint: Callable[[float], None]) -> None:
        """Llama a `paint(progreso)` a 60 fps hasta llegar a 1.

        El progreso no avanza mientras la ventana está en pausa. Con
        `seconds` 0 se dibuja una sola vez, ya completo.
        """
        elapsed = 0.0
        while not self.closed:
            dt = self._tick()
            if self.closed:
                return
            if not self._paused:
                elapsed += dt
            progress = 1.0 if seconds <= 0 else min(1.0, elapsed / seconds)
            paint(progress)
            if progress >= 1.0:
                return

    def _tick(self) -> float:
        """Espera al siguiente fotograma, atiende eventos y devuelve dt."""
        assert self._clock is not None
        dt = self._clock.tick(FPS) / 1000.0
        self._time += dt
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._close_window()
            elif event.type == pygame.KEYDOWN:
                self._key_pressed = True
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    self._close_window()
                elif event.key == pygame.K_SPACE:
                    self._paused = not self._paused
        return dt

    def _close_window(self) -> None:
        """El usuario cierra la ventana: desaparece ya, la terminal sigue."""
        self.closed = True
        self.close()

    # --- el fotograma ----------------------------------------------------

    def _paint(self, turn: int, progress: float,
               overlay: Optional[Callable[[], None]] = None) -> None:
        """Dibuja el mundo entre `turn - 1` y `turn` y un overlay opcional."""
        screen = self._screen
        if screen is None:
            return
        eased = self._ease(progress)
        before = self.scene.spots[max(0, turn - 1)]
        after = self.scene.spots[turn]
        # La ocupación cambia a mitad de viaje, cuando el dron "llega".
        shown = turn if progress >= 0.5 or turn == 0 else turn - 1
        screen.blit(self._background, (0, 0))
        self._draw_stars(screen)
        self._draw_links(screen, turn, progress)
        self._draw_zones(screen, shown)
        self._draw_drones(screen, before, after, eased)
        self._draw_effects(screen)
        self._draw_labels(screen)
        if overlay is not None:
            overlay()
        pygame.display.flip()

    @staticmethod
    def _ease(p: float) -> float:
        """Aceleración y frenada suaves (cúbica)."""
        return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2

    # --- fondo -----------------------------------------------------------

    def _make_background(self, size: Tuple[int, int]) -> pygame.Surface:
        """Degradado radial y rejilla tenue, dibujados una sola vez."""
        width, height = size
        background = pygame.Surface(size)
        background.fill(BACKGROUND)
        radius = int(max(width, height) * 0.75)
        steps = 40
        for step in range(steps):
            k = step / steps
            shade = self._mix(BACKGROUND, BACKGROUND_GLOW, k ** 1.6)
            pygame.draw.circle(background, shade,
                               (width // 2, int(height * 0.45)),
                               int(radius * (1 - k)))
        grid = self._mix(BACKGROUND, LINK, 0.08)
        for x in range(0, width, 48):
            pygame.draw.line(background, grid, (x, 0), (x, height))
        for y in range(0, height, 48):
            pygame.draw.line(background, grid, (0, y), (width, y))
        return background

    def _draw_stars(self, screen: pygame.Surface) -> None:
        """Estrellas que titilan cada una a su ritmo."""
        for x, y, depth, phase in self._stars:
            twinkle = 0.45 + 0.55 * math.sin(self._time * 1.3 + phase)
            level = int(40 + 150 * depth * twinkle)
            size = 2 if depth > 0.8 else 1
            screen.fill((level, level, min(255, level + 30)),
                        (int(x), int(y), size, size))

    # --- conexiones --------------------------------------------------------

    def _draw_links(self, screen: pygame.Surface, turn: int,
                    progress: float) -> None:
        """Conexiones; las usadas este turno, con un flujo de luz."""
        for conn in self.scene.graph.connections:
            a = self._proj.point(self.scene.points[conn.zone_a.name])
            b = self._proj.point(self.scene.points[conn.zone_b.name])
            types = (conn.zone_a.zone_type, conn.zone_b.zone_type)
            width = 2 + min(conn.max_link_capacity, 5)
            pygame.draw.line(screen, LINK_SHADOW, a, b, width + 4)
            if ZoneType.BLOCKED in types:
                pygame.draw.line(screen, self._mix(LINK_SHADOW, HOT, 0.35),
                                 a, b, 2)
            elif ZoneType.RESTRICTED in types:
                self._dashed(screen, TYPE_COLOR[ZoneType.RESTRICTED], a, b,
                             max(2, width // 2))
            else:
                pygame.draw.line(screen, self._mix(LINK_SHADOW, LINK, 0.7),
                                 a, b, max(2, width // 2))
        if progress >= 1.0 or turn == 0:
            return
        for use in self.scene.used[turn]:
            start = self._proj.point(self.scene.points[use.origin])
            end = self._proj.point(self.scene.points[use.target])
            color = Palette.drone_color(use.drone_id)
            length = math.dist(start, end)
            dots = max(3, int(length / 26))
            for index in range(dots):
                f = (index / dots + self._time * 1.4) % 1.0
                point = (start[0] + (end[0] - start[0]) * f,
                         start[1] + (end[1] - start[1]) * f)
                self._glow.draw(screen, color, point, 9)
                pygame.draw.circle(screen, self._mix(color, TEXT, 0.4),
                                   point, 2.5)

    def _dashed(self, screen: pygame.Surface, color: RGB, a: Pixel,
                b: Pixel, width: int) -> None:
        """Línea a trazos: las que llevan a una zona restricted."""
        length = math.dist(a, b)
        if length == 0:
            return
        dash, gap = 9.0, 7.0
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        pos = 0.0
        while pos < length:
            end = min(pos + dash, length)
            pygame.draw.line(screen, color,
                             (a[0] + ux * pos, a[1] + uy * pos),
                             (a[0] + ux * end, a[1] + uy * end), width)
            pos += dash + gap

    # --- zonas -------------------------------------------------------------

    def _draw_zones(self, screen: pygame.Surface, frame: int) -> None:
        """Cada zona con su tipo, su color y su ocupación."""
        occupants = self.scene.occupants[frame]
        for zone in self.scene.graph.zones.values():
            center = self._proj.point(self.scene.points[zone.name])
            color = self._zone_color(zone)
            count = len(occupants.get(zone.name, []))
            if self.scene.is_hub(zone.name):
                self._draw_hub(screen, zone, center, color, count, frame)
            else:
                self._draw_hex_zone(screen, zone, center, color, count)

    def _draw_hub(self, screen: pygame.Surface, zone: Zone, center: Pixel,
                  color: RGB, count: int, frame: int) -> None:
        """start_hub y end_hub: plataformas con una baliza que late."""
        r = self._radius * 1.35
        beat = (self._time * 0.8) % 1.0
        self._glow.draw(screen, color, center, r * 2.2)
        pygame.draw.circle(screen, self._mix(color, BACKGROUND, beat),
                           center, r * (1 + beat * 1.1), 2)
        pygame.draw.circle(screen, ZONE_FILL, center, r)
        pygame.draw.circle(screen, color, center, r, 3)
        self._arc_ring(screen, color, center, r * 0.72, self._time * 0.6, 8)
        value = (self.scene.delivered[frame] if zone.name == self.scene.goal
                 else count)
        text = self._fonts.render(self._fonts.strong, str(value), color)
        screen.blit(text, text.get_rect(center=(int(center[0]),
                                                int(center[1]))))

    def _draw_hex_zone(self, screen: pygame.Surface, zone: Zone,
                       center: Pixel, color: RGB, count: int) -> None:
        """Zona normal, priority, restricted o blocked."""
        r = self._radius
        full = zone.max_drones != UNLIMITED and count >= zone.max_drones > 0
        edge = HOT if full else color
        if full:
            pulse = 0.5 + 0.5 * math.sin(self._time * 8)
            self._glow.draw(screen, HOT, center, r * (2.0 + 0.4 * pulse))
        else:
            self._glow.draw(screen, color, center, r * 1.7)
        hexagon = [
            (center[0] + r * math.cos(math.pi / 6 + i * math.pi / 3),
             center[1] + r * math.sin(math.pi / 6 + i * math.pi / 3))
            for i in range(6)
        ]
        blocked = zone.zone_type is ZoneType.BLOCKED
        fill = self._mix(ZONE_FILL, HOT, 0.25) if blocked else ZONE_FILL
        pygame.draw.polygon(screen, fill, hexagon)
        pygame.draw.polygon(screen, edge, hexagon, 2)
        if zone.zone_type is ZoneType.RESTRICTED:
            self._arc_ring(screen, TYPE_COLOR[ZoneType.RESTRICTED], center,
                           r * 1.35, self._time * 0.8, 12)
        elif zone.zone_type is ZoneType.PRIORITY and count == 0:
            self._star(screen, GOLD, center, r * 0.45)
        elif blocked:
            k = r * 0.42
            pygame.draw.line(screen, HOT, (center[0] - k, center[1] - k),
                             (center[0] + k, center[1] + k), 3)
            pygame.draw.line(screen, HOT, (center[0] + k, center[1] - k),
                             (center[0] - k, center[1] + k), 3)
        if not blocked and zone.max_drones != UNLIMITED:
            self._capacity(screen, center, int(zone.max_drones), count, full)

    def _capacity(self, screen: pygame.Surface, center: Pixel, cap: int,
                  count: int, full: bool) -> None:
        """Un punto por plaza encima de la zona; llenos, en blanco o rojo."""
        r = self._radius
        if cap > 8:
            text = self._fonts.render(self._fonts.tiny, f"{count}/{cap}",
                                      HOT if full else TEXT)
            screen.blit(text, text.get_rect(
                midbottom=(int(center[0]), int(center[1] - r - 3))))
            return
        span = min(math.pi * 0.9, cap * 0.3)
        for index in range(cap):
            angle = -math.pi / 2 + (
                0.0 if cap == 1 else -span / 2 + span * index / (cap - 1))
            point = (center[0] + (r + 7) * math.cos(angle),
                     center[1] + (r + 7) * math.sin(angle))
            if index < count:
                pygame.draw.circle(screen, HOT if full else TEXT, point, 3)
            else:
                pygame.draw.circle(screen, self._mix(BACKGROUND, TEXT, 0.25),
                                   point, 3)

    def _zone_color(self, zone: Zone) -> RGB:
        """El `color=` del mapa (visible sobre el fondo), o el del tipo."""
        if zone.color is not None:
            rgb = Palette.resolve(zone.color, int(self._time * 8))
            if rgb is not None:
                return self._visible(rgb)
        if zone.name == self.scene.start:
            return GOOD
        if zone.name == self.scene.goal:
            return PINK
        return TYPE_COLOR[zone.zone_type]

    def _draw_labels(self, screen: pygame.Surface) -> None:
        """Nombres bajo las zonas; primero los hubs y sin solaparse."""
        placed: List[pygame.Rect] = []
        zones = sorted(self.scene.graph.zones.values(),
                       key=lambda z: not self.scene.is_hub(z.name))
        for zone in zones:
            hub = self.scene.is_hub(zone.name)
            center = self._proj.point(self.scene.points[zone.name])
            r = self._radius * (1.35 if hub else 1.0)
            text = self._fonts.render(
                self._fonts.small if hub else self._fonts.tiny,
                zone.name.upper() if hub else zone.name,
                self._zone_color(zone) if hub else DIM)
            rect = text.get_rect(midtop=(int(center[0]),
                                         int(center[1] + r + 6)))
            if any(rect.inflate(10, 2).colliderect(other)
                   for other in placed):
                continue
            placed.append(rect)
            screen.blit(text, rect)

    # --- drones ------------------------------------------------------------

    def _draw_drones(self, screen: pygame.Surface, before: Dict[int, Spot],
                     after: Dict[int, Spot], eased: float) -> None:
        """Cada dron entre su sitio de antes y el de después."""
        for drone in self.scene.ids:
            a, b = before[drone], after[drone]
            if a.delivered and b.delivered:
                self._trails[drone].clear()
                continue
            pa, pb = self._spot_pixel(a), self._spot_pixel(b)
            x = pa[0] + (pb[0] - pa[0]) * eased
            y = pa[1] + (pb[1] - pa[1]) * eased
            air = float(a.airborne) + (float(b.airborne)
                                       - float(a.airborne)) * eased
            # Al entregarse, el dron se encoge dentro del objetivo.
            scale = 1.0
            if b.delivered:
                scale = max(0.0, 1.0 - max(0.0, eased - 0.6) / 0.4)
            self._draw_trail(screen, drone, (x, y - air * self._drone * 1.6))
            if scale > 0.05:
                self._draw_drone(screen, drone, (x, y), air, scale)

    def _spot_pixel(self, spot: Spot) -> Pixel:
        """El píxel de un sitio: el centro, o su hueco en el anillo."""
        x, y = self._proj.point(spot.anchor)
        if spot.zone is None or (spot.crowd == 1
                                 and not self.scene.is_hub(spot.zone)):
            return x, y
        ring, index = divmod(spot.slot, 12)
        count = min(12, spot.crowd - ring * 12)
        angle = -math.pi / 2 + 2 * math.pi * index / count + ring * 0.26
        base = self._radius * (1.35 if self.scene.is_hub(spot.zone) else 1)
        distance = base + self._drone * 1.9 + ring * self._drone * 2.3
        return x + distance * math.cos(angle), y + distance * math.sin(angle)

    def _draw_trail(self, screen: pygame.Surface, drone: int,
                    point: Pixel) -> None:
        """Estela: puntos que se apagan hacia el fondo."""
        trail = self._trails[drone]
        if not trail or math.dist(trail[-1], point) > 1.5:
            trail.append(point)
        elif trail:
            trail.popleft()
        color = Palette.drone_color(drone)
        for index, spot in enumerate(trail):
            k = (index + 1) / len(trail)
            pygame.draw.circle(screen, self._mix(BACKGROUND, color, k * 0.6),
                               spot, max(1.0, self._drone * 0.45 * k))

    def _draw_drone(self, screen: pygame.Surface, drone: int, ground: Pixel,
                    air: float, scale: float) -> None:
        """Un cuadricóptero: cuerpo, cuatro brazos y hélices que giran.

        En el aire (tránsito hacia una restricted) se eleva y proyecta
        sombra sobre la conexión.
        """
        size = self._drone * scale * (1 + air * 0.25)
        lift = air * self._drone * 1.6
        bob = math.sin(self._time * 3 + drone) * 1.2
        x, y = ground[0], ground[1] - lift + bob
        color = Palette.drone_color(drone)
        if air > 0.05:
            shadow = pygame.Rect(0, 0, size * 2.6, size * 0.9)
            shadow.center = (int(ground[0]), int(ground[1] + 2))
            pygame.draw.ellipse(screen, self._mix(BACKGROUND, (0, 0, 0), 0.5),
                                shadow)
        self._glow.draw(screen, color, (x, y), size * (2.4 + air))
        arm = size * 1.35
        rotor = max(2.0, size * 0.55)
        spin = self._time * 25 + drone * 1.7
        blade = (math.cos(spin) * rotor, math.sin(spin) * rotor)
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            tip = (x + dx * arm, y + dy * arm)
            pygame.draw.line(screen, color, (x, y), tip,
                             max(1, int(size * 0.3)))
            pygame.draw.circle(screen, self._mix(color, BACKGROUND, 0.35),
                               tip, rotor, 1)
            pygame.draw.line(screen, (235, 240, 255),
                             (tip[0] - blade[0], tip[1] - blade[1]),
                             (tip[0] + blade[0], tip[1] + blade[1]), 1)
        pygame.draw.circle(screen, color, (x, y), size)
        pygame.draw.circle(screen, self._mix(color, TEXT, 0.6), (x, y),
                           size, 1)
        if size >= 6:
            label = self._fonts.render(self._fonts.tiny, str(drone),
                                       BACKGROUND)
            screen.blit(label, label.get_rect(center=(int(x), int(y) + 1)))

    # --- efectos -------------------------------------------------------------

    def _deliveries(self, turn: int) -> None:
        """Chispas y un "+1" por cada dron entregado en `turn`."""
        goal = self._proj.point(self.scene.points[self.scene.goal])
        for drone in self.scene.newly_delivered(turn):
            color = Palette.drone_color(drone)
            for _ in range(26):
                angle = self._rng.random() * math.tau
                speed = 40 + self._rng.random() * 130
                self._particles.append(Particle(
                    goal[0], goal[1], math.cos(angle) * speed,
                    math.sin(angle) * speed, color))
            self._popups.append([goal[0], goal[1], 1.0])

    def _draw_effects(self, screen: pygame.Surface) -> None:
        """Chispas, "+1" y el pulso de radar de las replanificaciones."""
        dt = 1.0 / FPS
        alive: List[Particle] = []
        for spark in self._particles:
            spark.life -= dt * 1.3
            if spark.life <= 0:
                continue
            spark.x += spark.vx * dt
            spark.y += spark.vy * dt
            spark.vx *= 0.94
            spark.vy *= 0.94
            pygame.draw.circle(screen,
                               self._mix(BACKGROUND, spark.color, spark.life),
                               (spark.x, spark.y), 1 + 2.5 * spark.life)
            alive.append(spark)
        self._particles = alive
        for popup in self._popups:
            popup[2] -= dt * 0.9
            if popup[2] > 0:
                text = self._fonts.render(
                    self._fonts.strong, "+1",
                    self._mix(BACKGROUND, GOOD, popup[2]))
                rise = (1 - popup[2]) * 40
                screen.blit(text, text.get_rect(
                    center=(int(popup[0]), int(popup[1] - 45 - rise))))
        self._popups = [p for p in self._popups if p[2] > 0]
        width, height = screen.get_size()
        for index, life in enumerate(self._pings):
            life -= dt * 0.8
            self._pings[index] = life
            if life <= 0:
                continue
            color = self._mix(BACKGROUND, PINK, life * 0.8)
            radius = (1 - life) * max(width, height) * 0.7
            pygame.draw.circle(screen, color, (width // 2, height // 2),
                               max(1.0, radius), 2)
            text = self._fonts.render(self._fonts.small, "WHCA* REPLAN",
                                      self._mix(BACKGROUND, PINK, life))
            screen.blit(text, text.get_rect(center=(width // 2, TOP - 12)))
        self._pings = [life for life in self._pings if life > 0]

    def _panel(self, screen: pygame.Surface,
               rect: pygame.Rect) -> pygame.Rect:
        """Un panel translúcido con borde para las tarjetas."""
        glass = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(glass, (*PANEL, 215), glass.get_rect(),
                         border_radius=14)
        pygame.draw.rect(glass, (*EDGE, 150), glass.get_rect(), 1,
                         border_radius=14)
        screen.blit(glass, rect.topleft)
        return rect

    # --- tarjetas ----------------------------------------------------------

    def _draw_briefing(self, value: str, progress: float) -> None:
        """Briefing de la misión con la cuenta atrás en grande."""
        screen = self._screen
        assert screen is not None
        fonts = self._fonts
        self._dim(screen)
        width, height = screen.get_size()
        box = pygame.Rect(0, 0, 520, 380)
        box.center = (width // 2, height // 2)
        self._panel(screen, box)
        head = fonts.render(fonts.small, "M I S S I O N   B R I E F I N G",
                            PINK)
        screen.blit(head, head.get_rect(midtop=(box.centerx, box.y + 24)))
        name = fonts.render(fonts.title, self.title[:26], TEXT)
        screen.blit(name, name.get_rect(midtop=(box.centerx, box.y + 50)))
        graph = self.scene.graph
        par = "-" if self.target is None else f"{self.target} turns"
        rows = (("SQUAD", f"{len(self.scene.ids)} drones"),
                ("NETWORK", f"{len(graph.zones)} zones · "
                            f"{len(graph.connections)} links"),
                ("ENGINE", f"WHCA* · window {self.window}"),
                ("PAR", par))
        for index, (key, val) in enumerate(rows):
            y = box.y + 104 + index * 24
            screen.blit(fonts.render(fonts.small, key, DIM), (box.x + 110, y))
            screen.blit(fonts.render(fonts.small, val, TEXT), (box.x + 210, y))
        color = GOOD if value == "GO" else CYAN
        count = fonts.render(fonts.huge, value, color)
        grow = 1.0 + 0.8 * (1 - self._ease(min(1.0, progress * 1.6)))
        size = (int(count.get_width() * grow), int(count.get_height() * grow))
        count = pygame.transform.smoothscale(count, size)
        screen.blit(count, count.get_rect(center=(box.centerx,
                                                  box.y + 290)))

    def _draw_end_card(self, metrics: Metrics) -> None:
        """MISSION COMPLETE: turnos y las métricas de movimientos."""
        screen = self._screen
        assert screen is not None
        fonts = self._fonts
        self._dim(screen)
        width, height = screen.get_size()
        box = pygame.Rect(0, 0, 560, 340)
        box.center = (width // 2, height // 2)
        self._panel(screen, box)
        over = self.target is not None and metrics.turns > self.target
        color = WARN if over else GOOD
        head = fonts.render(fonts.small, "M I S S I O N   C O M P L E T E",
                            PINK)
        screen.blit(head, head.get_rect(midtop=(box.centerx, box.y + 22)))
        verdict = "OVER PAR" if over else "ALL DRONES DELIVERED"
        text = fonts.render(fonts.strong, verdict, color)
        screen.blit(text, text.get_rect(midtop=(box.centerx, box.y + 48)))
        turns = fonts.render(fonts.huge, str(metrics.turns), CYAN)
        spot = (box.centerx - 40, box.y + 140)
        screen.blit(turns, turns.get_rect(center=spot))
        unit = fonts.render(fonts.strong, "TURNS", DIM)
        screen.blit(unit, unit.get_rect(
            midleft=(spot[0] + turns.get_width() // 2 + 10, spot[1] + 20)))
        cells = (("MOVES", str(metrics.total_moves)),
                 ("MOVES/TURN", f"{metrics.avg_moves_per_turn:.2f}"),
                 ("AVG DELIVERY", f"T{metrics.avg_turns_per_drone:.1f}"),
                 ("WAITS", str(metrics.total_waits)),
                 ("PEAK AIRBORNE", str(metrics.peak_airborne)),
                 ("COMPUTE", f"{metrics.seconds * 1000:.0f} ms"))
        for index, (key, val) in enumerate(cells):
            x = box.x + 50 + (index % 3) * 170
            y = box.y + 218 + (index // 3) * 44
            screen.blit(fonts.render(fonts.tiny, key, DIM), (x, y))
            screen.blit(fonts.render(fonts.strong, val, TEXT), (x, y + 14))
        hint = fonts.render(fonts.tiny, "press any key or close the window",
                            DIM)
        screen.blit(hint, hint.get_rect(midbottom=(box.centerx,
                                                   box.bottom - 8)))

    def _dim(self, screen: pygame.Surface) -> None:
        """Oscurece el mapa detrás de una tarjeta."""
        veil = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        veil.fill((*BACKGROUND, 150))
        screen.blit(veil, (0, 0))

    # --- dibujo genérico ---------------------------------------------------

    def _arc_ring(self, screen: pygame.Surface, color: RGB, center: Pixel,
                  radius: float, angle: float, pieces: int) -> None:
        """Anillo a trazos que gira con `angle`."""
        rect = pygame.Rect(0, 0, radius * 2, radius * 2)
        rect.center = (int(center[0]), int(center[1]))
        step = math.tau / pieces
        for index in range(pieces):
            start = angle + index * step
            pygame.draw.arc(screen, color, rect, start, start + step * 0.55,
                            2)

    @staticmethod
    def _star(screen: pygame.Surface, color: RGB, center: Pixel,
              radius: float) -> None:
        """Estrella de cinco puntas."""
        points = []
        for index in range(10):
            r = radius if index % 2 == 0 else radius * 0.45
            angle = -math.pi / 2 + index * math.pi / 5
            points.append((center[0] + r * math.cos(angle),
                           center[1] + r * math.sin(angle)))
        pygame.draw.polygon(screen, color, points)

    @staticmethod
    def _mix(a: RGB, b: RGB, k: float) -> RGB:
        """El color que está a una fracción `k` del camino de `a` a `b`."""
        k = max(0.0, min(1.0, k))
        return (int(a[0] + (b[0] - a[0]) * k),
                int(a[1] + (b[1] - a[1]) * k),
                int(a[2] + (b[2] - a[2]) * k))

    @staticmethod
    def _visible(rgb: RGB) -> RGB:
        """Aclara los colores muy oscuros (black, maroon) sobre el fondo."""
        light = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255
        if light >= 0.22:
            return rgb
        return PygameView._mix(rgb, (255, 255, 255), 0.55 - light)
