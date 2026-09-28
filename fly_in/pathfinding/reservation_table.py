"""Tabla de reservas espacio-temporal (SP06).

Convención de tiempo (compartida con SP07 y SP08):

- El "instante t" es el estado tras ejecutar t turnos. El instante 0 es el
  inicial (todos los drones en start_hub). La línea k de la salida es el
  paso del instante k-1 al instante k.
- Zona (z, t): drones que están en z en el instante t.
- Conexión (c, t): drones que están cruzando c entre el instante t y t+1.
- Un movimiento que sale de `frm` en el instante T hacia `to` (coste c)
  ocupa la conexión en T … T+c-1 y la zona `to` en el instante T+c. No ocupa
  ninguna zona en los instantes intermedios: está en el aire.
"""

from typing import AbstractSet, Dict, List, Tuple, TypeVar

from fly_in.models.connection import Connection
from fly_in.models.graph import Graph
from fly_in.models.zone import Zone

ZoneKey = Tuple[str, int]
MoveKey = Tuple[str, str, int]
Key = TypeVar("Key", ZoneKey, MoveKey)


class ReservationError(Exception):
    """Se intentó reservar algo que no cabe.

    Nunca debería ocurrir: el planificador pregunta antes de reservar. Si
    salta, hay un bug en quien llama, y es mejor enterarse aquí que tres
    turnos después como una colisión inexplicable.
    """


class ReservationTable:
    """Ocupación espacio-temporal de zonas y conexiones.

    Guarda QUIÉN (id de dron) ocupa cada zona y conexión en cada instante;
    la ocupación es la longitud de esa lista. start_hub y end_hub nunca se
    llenan porque su max_drones es UNLIMITED.
    """

    def __init__(self, graph: Graph) -> None:
        """Crea una tabla vacía para `graph`."""
        self._graph = graph
        self._zones: Dict[ZoneKey, List[int]] = {}
        self._links: Dict[ZoneKey, List[int]] = {}
        self._moves: Dict[MoveKey, List[int]] = {}

    # --- consultas -----------------------------------------------------

    def zone_has_room(self, zone: Zone, turn: int) -> bool:
        """¿Cabe un dron más en `zone` en el instante `turn`?"""
        occupants = self._zones.get((zone.name, turn), [])
        return len(occupants) < zone.max_drones

    def link_has_room(self, conn: Connection, turn: int) -> bool:
        """¿Cabe un dron más cruzando `conn` entre `turn` y `turn + 1`?"""
        occupants = self._links.get((conn.name, turn), [])
        return len(occupants) < conn.max_link_capacity

    def would_swap(self, frm: Zone, to: Zone, turn: int) -> bool:
        """¿Hay un dron cruzando en sentido `to → frm` entre `turn` y +1?"""
        return (to.name, frm.name, turn) in self._moves

    def can_move(self, frm: Zone, to: Zone, turn: int) -> bool:
        """¿Puede un dron salir de `frm` en `turn` y llegar a `to`?

        Comprueba todo lo que el movimiento ocupa: la conexión y el sentido
        en cada instante del trayecto, y la zona destino a la llegada.

        Raises:
            ValueError: Si `frm` y `to` no están conectadas.
        """
        conn = self._graph.connection_between(frm, to)
        if not to.is_traversable():
            return False
        cost = to.movement_cost()
        for slot in range(turn, turn + cost):
            if not self.link_has_room(conn, slot):
                return False
            if self.would_swap(frm, to, slot):
                return False
        return self.zone_has_room(to, turn + cost)

    def zone_occupants(self, zone: Zone, turn: int) -> List[int]:
        """Ids de los drones en `zone` en el instante `turn` (copia)."""
        return list(self._zones.get((zone.name, turn), []))

    def link_occupants(self, conn: Connection, turn: int) -> List[int]:
        """Ids de los drones cruzando `conn` entre `turn` y +1 (copia)."""
        return list(self._links.get((conn.name, turn), []))

    # --- escritura -----------------------------------------------------

    def reserve_move(
        self, drone_id: int, frm: Zone, to: Zone, turn: int
    ) -> None:
        """Reserva el movimiento de `drone_id` de `frm` a `to` saliendo en
        `turn`: la conexión en turn … turn+coste-1 y `to` en turn+coste.

        Es atómico: o se reserva todo, o no se toca nada.

        Raises:
            ReservationError: Si el movimiento no cabe.
            ValueError: Si `frm` y `to` no están conectadas.
        """
        if not self.can_move(frm, to, turn):
            raise ReservationError(
                f"D{drone_id}: move {frm.name}->{to.name} "
                f"leaving at turn {turn} does not fit"
            )
        conn = self._graph.connection_between(frm, to)
        cost = to.movement_cost()
        for slot in range(turn, turn + cost):
            self._add(self._links, (conn.name, slot), drone_id)
            self._add(self._moves, (frm.name, to.name, slot), drone_id)
        self._add(self._zones, (to.name, turn + cost), drone_id)

    def reserve_wait(self, drone_id: int, zone: Zone, turn: int) -> None:
        """Reserva que `drone_id` está en `zone` en el instante `turn`.

        Raises:
            ReservationError: Si la zona está llena en ese instante.
        """
        if not self.zone_has_room(zone, turn):
            raise ReservationError(
                f"D{drone_id}: zone {zone.name} is full at turn {turn}"
            )
        self._add(self._zones, (zone.name, turn), drone_id)

    def clear_from(
        self, turn: int, keep: AbstractSet[int] = frozenset()
    ) -> None:
        """Descarta las reservas de `turn` en adelante.

        Las anteriores a `turn` son historia ya ejecutada y se conservan.
        Las de los drones en `keep` se conservan enteras: son drones en el
        aire, cuya llegada ya está comprometida y no se puede replanificar.
        """
        self._zones = self._cleared(self._zones, turn, keep)
        self._links = self._cleared(self._links, turn, keep)
        self._moves = self._cleared(self._moves, turn, keep)

    # --- internos ------------------------------------------------------

    @staticmethod
    def _add(table: Dict[Key, List[int]], key: Key, drone_id: int) -> None:
        """Apunta a `drone_id` en `key`.

        Raises:
            ReservationError: Si ese dron ya estaba apuntado ahí: contarlo
                dos veces falsearía la ocupación.
        """
        occupants = table.setdefault(key, [])
        if drone_id in occupants:
            raise ReservationError(f"D{drone_id} already reserved {key}")
        occupants.append(drone_id)

    @staticmethod
    def _cleared(
        table: Dict[Key, List[int]], turn: int, keep: AbstractSet[int]
    ) -> Dict[Key, List[int]]:
        """Copia de `table` sin las reservas >= `turn` salvo las de `keep`.

        Construye un diccionario nuevo en lugar de borrar mientras recorre:
        borrar durante la iteración lanza RuntimeError.
        """
        result: Dict[Key, List[int]] = {}
        for key, occupants in table.items():
            if key[-1] < turn:
                result[key] = list(occupants)
                continue
            kept = [drone for drone in occupants if drone in keep]
            if kept:
                result[key] = kept
        return result
