"""Qué hay en pantalla en cada turno, sin dibujar nada (SP10).

`Scene` traduce la grabación (`ReplayRecorder`) a lo que la ventana pygame
necesita: dónde va cada dron en cada fotograma, qué conexiones se usan al
pasar de un turno al siguiente y cuántos drones se han entregado. Se calcula
una vez al empezar; durante la animación solo se consulta.

No importa pygame, así que se prueba sin pantalla.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from fly_in.models.graph import Graph
from fly_in.simulation.simulator import Replan
from fly_in.visualization.recorder import Position

MapPoint = Tuple[float, float]   # coordenadas del fichero de mapa


@dataclass(frozen=True)
class Spot:
    """Dónde dibujar un dron en un fotograma.

    `anchor` es un punto del mapa: una zona, o el punto medio de una
    conexión si el dron está en el aire. Si varios drones comparten zona,
    `slot` y `crowd` dicen qué hueco del anillo alrededor de la zona le toca
    (la ventana lo convierte en píxeles).
    """

    anchor: MapPoint
    zone: Optional[str]   # None en el aire o entregado
    airborne: bool
    delivered: bool
    slot: int = 0
    crowd: int = 1


@dataclass(frozen=True)
class LinkUse:
    """Una conexión usada al pasar de un fotograma al siguiente."""

    origin: str
    target: str
    drone_id: int


class Scene:
    """Todos los fotogramas de una partida, listos para dibujarse."""

    def __init__(
        self,
        graph: Graph,
        positions: Sequence[Dict[str, Position]],
        lines: Sequence[str],
        replans: Sequence[Replan] = (),
    ) -> None:
        """Precalcula los fotogramas de la grabación `positions`."""
        assert graph.start_hub is not None and graph.end_hub is not None
        self.graph = graph
        self.start = graph.start_hub.name
        self.goal = graph.end_hub.name
        self.points: Dict[str, MapPoint] = {
            zone.name: (float(zone.x), float(zone.y))
            for zone in graph.zones.values()
        }
        self.ids: List[int] = sorted(int(key) for key in positions[0])
        self.lines: List[str] = list(lines)
        self.last = len(positions) - 1
        self.spots: List[Dict[int, Spot]] = [
            self._spots(frame) for frame in positions
        ]
        self.occupants: List[Dict[str, List[int]]] = [
            self._occupants(frame) for frame in positions
        ]
        self.delivered: List[int] = [
            sum(1 for pos in frame.values() if pos[0] == "d")
            for frame in positions
        ]
        self.airborne: List[int] = [
            sum(1 for pos in frame.values() if pos[0] == "a")
            for frame in positions
        ]
        self.used: List[List[LinkUse]] = [[]] + [
            self._used(positions[k - 1], positions[k])
            for k in range(1, len(positions))
        ]
        # Una replanificación en el instante T precede al turno T+1.
        self.replan_turns: Set[int] = {replan.turn + 1 for replan in replans}

    def is_hub(self, name: str) -> bool:
        """¿Es start_hub o end_hub?"""
        return name in (self.start, self.goal)

    def newly_delivered(self, frame: int) -> List[int]:
        """Drones que se entregan justo en el fotograma `frame`."""
        if frame <= 0:
            return []
        before, now = self.spots[frame - 1], self.spots[frame]
        return [
            drone for drone in self.ids
            if now[drone].delivered and not before[drone].delivered
        ]

    # --- internos ------------------------------------------------------

    def _spots(self, frame: Dict[str, Position]) -> Dict[int, Spot]:
        """El sitio de cada dron en un fotograma."""
        crowds: Dict[str, List[int]] = {}
        for drone in self.ids:
            pos = frame[str(drone)]
            if pos[0] == "z":
                crowds.setdefault(pos[1], []).append(drone)
        spots: Dict[int, Spot] = {}
        for drone in self.ids:
            pos = frame[str(drone)]
            if pos[0] == "a":
                (x0, y0), (x1, y1) = self.points[pos[1]], self.points[pos[2]]
                spots[drone] = Spot(((x0 + x1) / 2, (y0 + y1) / 2), None,
                                    airborne=True, delivered=False)
            elif pos[0] == "d":
                spots[drone] = Spot(self.points[self.goal], None,
                                    airborne=False, delivered=True)
            else:
                crowd = crowds[pos[1]]
                spots[drone] = Spot(self.points[pos[1]], pos[1],
                                    airborne=False, delivered=False,
                                    slot=crowd.index(drone),
                                    crowd=len(crowd))
        return spots

    def _occupants(self, frame: Dict[str, Position]) -> Dict[str, List[int]]:
        """Qué drones hay en cada zona (los del aire no ocupan ninguna)."""
        result: Dict[str, List[int]] = {}
        for drone in self.ids:
            pos = frame[str(drone)]
            if pos[0] == "z":
                result.setdefault(pos[1], []).append(drone)
        return result

    def _used(
        self, before: Dict[str, Position], after: Dict[str, Position]
    ) -> List[LinkUse]:
        """Conexiones recorridas del fotograma `before` al `after`."""
        used: List[LinkUse] = []
        for drone in self.ids:
            a, b = before[str(drone)], after[str(drone)]
            ends: Optional[Tuple[str, str]] = None
            if a[0] == "z" and b[0] == "z" and a[1] != b[1]:
                ends = (a[1], b[1])
            elif a[0] == "z" and b[0] == "a":
                ends = (b[1], b[2])
            elif a[0] == "a":
                ends = (a[1], a[2])
            elif a[0] == "z" and b[0] == "d":
                ends = (a[1], self.goal)
            if ends is not None:
                used.append(LinkUse(ends[0], ends[1], drone))
        return used
