"""The graphical window: the run animated with pygame (SP10).

The simulation is already over when the window opens: `Scene` holds every
frame. The window only **interpolates** between the frame of one turn and
the next, for the time `Session` asks for, while the terminal writes the
log of that same turn. It computes nothing of the algorithm.

It is a minimal view, meant to check that the run is correct: white
background, zones as pastel circles with a thin outline, drones as vivid
dots with a dark outline and their number. That way a drone is never
mistaken for a zone even when they share the same hue.

Important: pygame prints a greeting on **stdout** when imported. `Session`
sets `PYGAME_HIDE_SUPPORT_PROMPT` before importing this module, because
stdout is only for the lines of the subject.
"""

import math
import time
from types import TracebackType
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Type

import pygame

from fly_in.models.zone import UNLIMITED, Zone, ZoneType
from fly_in.simulation.metrics import Metrics
from fly_in.visualization.palette import RGB, Palette
from fly_in.visualization.scene import MapPoint, Scene, Spot

Pixel = Tuple[float, float]

FPS = 60
DEFAULT_SIZE = (1200, 760)
MIN_SIZE = (800, 560)
# Margins around the map (the status line goes at the top).
TOP, BOTTOM, SIDE = 56, 40, 60
MAX_SCALE = 170.0      # pixels per map unit, at most
MAX_STRETCH = 2.5      # how far one axis may stretch relative to the other
PASTEL = 0.62          # how much a zone's color is lightened towards white

WHITE: RGB = (255, 255, 255)
BLACK: RGB = (0, 0, 0)
INK: RGB = (40, 44, 52)
DIM: RGB = (120, 126, 138)
LINK: RGB = (200, 204, 212)
OUTLINE: RGB = (150, 156, 168)
FULL: RGB = (210, 50, 50)

# Color of each zone type when the map has no `color=` (before lightening).
TYPE_COLOR: Dict[ZoneType, RGB] = {
    ZoneType.NORMAL: (170, 176, 190),
    ZoneType.PRIORITY: (240, 200, 40),
    ZoneType.RESTRICTED: (240, 140, 40),
    ZoneType.BLOCKED: (90, 90, 96),
}
START_COLOR: RGB = (60, 190, 90)
GOAL_COLOR: RGB = (90, 140, 230)


class Projection:
    """From the map plane (y up) to pixels (y down).

    Each axis has its own scale to make the most of the window, but
    neither stretches more than `MAX_STRETCH` times the other: the map is
    still recognizable.
    """

    def __init__(self, points: Sequence[MapPoint], size: Tuple[int, int]):
        """Fit `points` in a window of `size` pixels."""
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
        # Zone radius: large if there is room, small if zones are close.
        spacing = min(self.scale_x if span_x else MAX_SCALE,
                      self.scale_y if span_y else MAX_SCALE)
        self.radius = max(10.0, min(26.0, spacing * 0.3))

    def point(self, point: MapPoint) -> Pixel:
        """The pixel of a map point."""
        return (self.origin_x + (point[0] - self.min_x) * self.scale_x,
                self.origin_y + (self.max_y - point[1]) * self.scale_y)


class PygameView:
    """The window: open it, animate each turn, close with the summary.

    It is a context manager: leaving the `with` shuts pygame down even on
    an error or Ctrl+C. If the user closes the window halfway, `closed`
    becomes True and the remaining calls do nothing: the terminal goes on.
    """

    def __init__(self, scene: Scene, title: str, window: int,
                 target: Optional[int] = None) -> None:
        """Set up the window (without opening it yet)."""
        self.scene = scene
        self.title = title
        self.window = window
        self.target = target
        self.closed = False
        self._screen: Optional[pygame.Surface] = None
        self._clock: Optional[pygame.time.Clock] = None
        self._frame = 0           # last completed frame
        self._paused = False
        self._key_pressed = False

    # --- lifecycle -----------------------------------------------------

    def __enter__(self) -> "PygameView":
        """The window, to be used inside the `with`."""
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Shut pygame down no matter what."""
        self.close()

    def open(self) -> bool:
        """Open the window. False if it cannot.

        pygame fails with `pygame.error` if there is no video, and with
        `NotImplementedError` if a module is missing (e.g. fonts in an
        incomplete installation). In both cases the run goes on in the
        terminal.
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
            self._font = pygame.font.SysFont("dejavusans,arial,sans", 14)
            self._bold = pygame.font.SysFont("dejavusans,arial,sans", 16,
                                             bold=True)
        except (pygame.error, NotImplementedError):
            self.close()
            return False
        self._clock = pygame.time.Clock()
        self._proj = Projection(list(self.scene.points.values()), size)
        self._radius = self._proj.radius
        self._drone = max(7.0, self._radius * 0.5)
        return True

    def close(self) -> None:
        """Close the window and pygame (it can be called several times)."""
        self._screen = None
        if pygame.get_init():
            pygame.quit()

    # --- what Session asks for -----------------------------------------

    def countdown(self, value: str, seconds: float) -> None:
        """The map at turn 0 with the countdown on the status line."""
        status = "GO" if value == "GO" else f"starting in {value}"
        self._animate(seconds, lambda p: self._paint(0, 1.0, status))

    def show_frame(self, turn: int) -> None:
        """Show frame `turn` still (without animating)."""
        if self.closed:
            return
        self._paint(turn, 1.0)
        self._frame = turn

    def play_turn(self, turn: int, seconds: float) -> None:
        """Animate from frame `turn - 1` to `turn` in `seconds`."""
        if self.closed:
            return
        self._animate(seconds, lambda p: self._paint(turn, p))
        self._frame = turn

    def finish(self, metrics: Metrics, hold: float) -> None:
        """Summary on the status line until a key press or `hold` s."""
        if self.closed or hold <= 0:
            return
        status = (f"done in {metrics.turns} turns"
                  + ("" if self.target is None
                     else f" (target {self.target})")
                  + " · press any key to close")
        self._key_pressed = False
        started = time.perf_counter()
        while not self.closed and not self._key_pressed:
            if time.perf_counter() - started >= hold:
                return
            self._tick()
            self._paint(self._frame, 1.0, status)

    def save_screenshot(self, path: str) -> None:
        """Save what is in the window right now (for the documentation)."""
        if self._screen is not None:
            pygame.image.save(self._screen, path)

    # --- time and events -----------------------------------------------

    def _animate(self, seconds: float, paint: Callable[[float], None]) -> None:
        """Call `paint(progress)` at 60 fps until it reaches 1.

        Progress does not advance while the window is paused. With
        `seconds` 0 it draws a single time, already complete.
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
        """Wait for the next frame, handle events and return dt."""
        assert self._clock is not None
        dt: float = self._clock.tick(FPS) / 1000.0
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
        """The user closes the window: it goes away, the terminal goes on."""
        self.closed = True
        self.close()

    # --- the frame -------------------------------------------------------

    def _paint(self, turn: int, progress: float,
               status: Optional[str] = None) -> None:
        """Draw the world between `turn - 1` and `turn`."""
        screen = self._screen
        if screen is None:
            return
        eased = self._ease(progress)
        before = self.scene.spots[max(0, turn - 1)]
        after = self.scene.spots[turn]
        # Occupancy changes halfway through the trip, when the drone "arrives".
        shown = turn if progress >= 0.5 or turn == 0 else turn - 1
        screen.fill(WHITE)
        self._draw_links(screen)
        self._draw_zones(screen, shown)
        self._draw_drones(screen, before, after, eased)
        self._draw_status(screen, shown, status)
        pygame.display.flip()

    @staticmethod
    def _ease(p: float) -> float:
        """Smooth start and stop (smoothstep)."""
        return p * p * (3 - 2 * p)

    def _draw_status(self, screen: pygame.Surface, frame: int,
                     status: Optional[str]) -> None:
        """One line at the top: map, turn, delivered and keys."""
        parts = [
            self.title,
            f"turn {frame}/{self.scene.last}",
            f"delivered {self.scene.delivered[frame]}/{len(self.scene.ids)}",
        ]
        if self._paused:
            parts.append("PAUSED")
        parts.append(status or "SPACE pause · ESC close")
        text = self._font.render("   ·   ".join(parts), True, INK)
        screen.blit(text, (SIDE // 2, 18))
        pygame.draw.line(screen, LINK, (0, TOP - 14),
                         (screen.get_width(), TOP - 14))

    # --- connections ------------------------------------------------------

    def _draw_links(self, screen: pygame.Surface) -> None:
        """Gray lines; dashed for those leading to a restricted zone."""
        for conn in self.scene.graph.connections:
            a = self._proj.point(self.scene.points[conn.zone_a.name])
            b = self._proj.point(self.scene.points[conn.zone_b.name])
            types = (conn.zone_a.zone_type, conn.zone_b.zone_type)
            width = 1 + min(conn.max_link_capacity, 4)
            if ZoneType.RESTRICTED in types:
                self._dashed(screen, OUTLINE, a, b, max(2, width // 2))
            else:
                pygame.draw.line(screen, LINK, a, b, width)

    @staticmethod
    def _dashed(screen: pygame.Surface, color: RGB, a: Pixel, b: Pixel,
                width: int) -> None:
        """Dashed line."""
        length = math.dist(a, b)
        if length == 0:
            return
        dash, gap = 8.0, 6.0
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        pos = 0.0
        while pos < length:
            end = min(pos + dash, length)
            pygame.draw.line(screen, color,
                             (a[0] + ux * pos, a[1] + uy * pos),
                             (a[0] + ux * end, a[1] + uy * end), width)
            pos += dash + gap

    # --- zones -------------------------------------------------------------

    def _draw_zones(self, screen: pygame.Surface, frame: int) -> None:
        """Pastel circle, name below and occupancy if it has a limit.

        A name that would overlap one already written is skipped.
        """
        occupants = self.scene.occupants[frame]
        placed: List[pygame.Rect] = []
        # Hubs first: if two names overlap, the hub's wins.
        zones = sorted(self.scene.graph.zones.values(),
                       key=lambda z: not self.scene.is_hub(z.name))
        for zone in zones:
            center = self._proj.point(self.scene.points[zone.name])
            hub = self.scene.is_hub(zone.name)
            r = self._radius * (1.3 if hub else 1.0)
            count = len(occupants.get(zone.name, []))
            full = (zone.max_drones != UNLIMITED
                    and count >= zone.max_drones > 0)
            base = self._zone_color(zone)
            pygame.draw.circle(screen, self._mix(base, WHITE, PASTEL),
                               center, r)
            pygame.draw.circle(screen, FULL if full else OUTLINE, center, r,
                               2 if full else 1)
            if zone.zone_type is ZoneType.BLOCKED:
                k = r * 0.45
                for sx in (-1, 1):
                    pygame.draw.line(screen, DIM,
                                     (center[0] - k, center[1] - sx * k),
                                     (center[0] + k, center[1] + sx * k), 2)
            label = zone.name
            if zone.name == self.scene.goal:
                label += f"  {self.scene.delivered[frame]}"
            elif zone.max_drones != UNLIMITED and not hub:
                label += f"  {count}/{int(zone.max_drones)}"
            text = self._font.render(label, True, FULL if full else DIM)
            rect = text.get_rect(midtop=(int(center[0]),
                                         int(center[1] + r + 4)))
            rect.clamp_ip(screen.get_rect())
            if not any(rect.inflate(8, 0).colliderect(other)
                       for other in placed):
                placed.append(rect)
                screen.blit(text, rect)

    def _zone_color(self, zone: Zone) -> RGB:
        """The map's `color=`, or the one of the type / hub."""
        if zone.color is not None:
            rgb = Palette.resolve(zone.color)
            if rgb is not None:
                return rgb
        if zone.name == self.scene.start:
            return START_COLOR
        if zone.name == self.scene.goal:
            return GOAL_COLOR
        return TYPE_COLOR[zone.zone_type]

    # --- drones ------------------------------------------------------------

    def _draw_drones(self, screen: pygame.Surface, before: Dict[int, Spot],
                     after: Dict[int, Spot], eased: float) -> None:
        """Each drone between its place before and after."""
        for drone in self.scene.ids:
            a, b = before[drone], after[drone]
            if a.delivered and b.delivered:
                continue
            pa, pb = self._spot_pixel(a), self._spot_pixel(b)
            x = pa[0] + (pb[0] - pa[0]) * eased
            y = pa[1] + (pb[1] - pa[1]) * eased
            # When delivered, the drone shrinks into the goal.
            scale = 1.0
            if b.delivered:
                scale = max(0.0, 1.0 - max(0.0, eased - 0.7) / 0.3)
            if scale > 0.05:
                self._draw_drone(screen, drone, (x, y), scale)

    def _spot_pixel(self, spot: Spot) -> Pixel:
        """The pixel of a spot: the center, or its place on the ring."""
        x, y = self._proj.point(spot.anchor)
        if spot.zone is None or (spot.crowd == 1
                                 and not self.scene.is_hub(spot.zone)):
            return x, y
        ring, index = divmod(spot.slot, 12)
        count = min(12, spot.crowd - ring * 12)
        angle = -math.pi / 2 + 2 * math.pi * index / count + ring * 0.26
        base = self._radius * (1.3 if self.scene.is_hub(spot.zone) else 1)
        distance = base + self._drone * 1.4 + ring * self._drone * 2.2
        return x + distance * math.cos(angle), y + distance * math.sin(angle)

    def _draw_drone(self, screen: pygame.Surface, drone: int, center: Pixel,
                    scale: float) -> None:
        """Vivid dot with a dark outline and the drone number."""
        size = self._drone * scale
        color = self._on_white(Palette.drone_color(drone))
        pygame.draw.circle(screen, color, center, size)
        pygame.draw.circle(screen, INK, center, size, 2)
        if size >= 7:
            label = self._font.render(str(drone), True, WHITE)
            screen.blit(label, label.get_rect(
                center=(int(center[0]), int(center[1]))))

    # --- color ---------------------------------------------------------------

    @staticmethod
    def _mix(a: RGB, b: RGB, k: float) -> RGB:
        """The color a fraction `k` of the way from `a` to `b`."""
        k = max(0.0, min(1.0, k))
        return (int(a[0] + (b[0] - a[0]) * k),
                int(a[1] + (b[1] - a[1]) * k),
                int(a[2] + (b[2] - a[2]) * k))

    @staticmethod
    def _on_white(rgb: RGB) -> RGB:
        """Darken light colors (yellow) on the white background."""
        light = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255
        if light <= 0.55:
            return rgb
        return PygameView._mix(rgb, BLACK, light - 0.45)
