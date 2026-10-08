"""Tests for Drone and Simulator (SP08).

The validator `assert_simulation_is_legal` reads the trace like an
external evaluator: it only knows the graph and the rules of Chap. VII. It
uses neither ReservationTable nor anything from the simulator, so it does
not just check that the code agrees with itself.
"""

from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

import pytest

from fly_in.models.graph import Graph
from fly_in.models.zone import ZoneType
from fly_in.parsing.map_parser import MapParser
from fly_in.pathfinding.whca import Step
from fly_in.simulation.drone import Drone, DroneState
from fly_in.simulation.errors import SimulationError
from fly_in.simulation.simulator import Move, Simulator

MAPS_DIR = Path(__file__).resolve().parent.parent / "maps"
VALID_MAPS = sorted(
    str(p.relative_to(MAPS_DIR)) for p in (MAPS_DIR / "valid").glob("*.txt")
)
OFFICIAL_MAPS = sorted(
    str(p.relative_to(MAPS_DIR))
    for p in (MAPS_DIR / "oficial_maps").glob("*/*.txt")
)


def load(relative: str) -> Tuple[int, Graph]:
    """(nb_drones, graph) of a map from maps/."""
    return MapParser.parse((MAPS_DIR / relative).read_text())


def simulate(
    relative: str, window: int = 8
) -> Tuple[Simulator, List[List[Move]]]:
    """Simulate the map and return the simulator and the trace."""
    nb_drones, graph = load(relative)
    sim = Simulator(graph, nb_drones, window)
    return sim, sim.run()


def as_text(trace: Sequence[Sequence[Move]]) -> List[str]:
    """The trace in the format of Chap. VII.5 (what SP09 will do)."""
    return [
        " ".join(
            f"D{m.drone_id}-"
            + (m.target.name if m.arrives else m.connection.name)
            for m in moves
        )
        for moves in trace
    ]


# --- the independent validator -----------------------------------------

def assert_simulation_is_legal(
    graph: Graph, nb_drones: int, trace: Sequence[Sequence[Move]]
) -> None:
    """Walk the trace and check every rule of Chap. VII.2/VII.3.

    - No zone exceeds max_drones (start/end unlimited)
    - No connection exceeds max_link_capacity on any turn
    - No drone enters a blocked zone
    - Every move goes through a real connection between origin and target
    - A transit to a restricted zone lasts exactly 2 turns and is not
      interrupted; to a normal/priority zone, 1 turn
    - No drone appears twice in the same turn
    - Nobody crosses head-on through the same connection
    - Delivered drones never move again, and in the end all of them are
    """
    assert graph.start_hub is not None and graph.end_hub is not None
    at: Dict[int, str] = {i: graph.start_hub.name for i in
                          range(1, nb_drones + 1)}
    airborne: Dict[int, Tuple[str, str, str]] = {}   # id -> (orig, dst, conn)
    delivered: Set[int] = set()

    for number, moves in enumerate(trace, start=1):
        ids = [move.drone_id for move in moves]
        assert len(ids) == len(set(ids)), f"turn {number}: repeated drone"
        assert not delivered & set(ids), f"turn {number}: delivered moves"
        assert set(airborne) <= set(ids), (
            f"turn {number}: a drone stayed in the air"
        )

        on_link: Dict[str, int] = {}
        directions: Set[Tuple[str, str, str]] = set()
        for move in moves:
            origin, target = move.origin.name, move.target.name
            conn = graph.connection_between(move.origin, move.target)
            assert move.connection is conn, f"turn {number}: fake connection"
            assert target != origin
            assert move.target.zone_type is not ZoneType.BLOCKED
            assert at[move.drone_id] == origin, (
                f"turn {number}: D{move.drone_id} was not at {origin}"
            )
            restricted = move.target.zone_type is ZoneType.RESTRICTED

            if move.drone_id in airborne:
                assert airborne.pop(move.drone_id) == (
                    origin, target, conn.name
                ), f"turn {number}: D{move.drone_id} changed course"
                assert move.arrives, "third turn in the air"
            elif restricted:
                assert not move.arrives, "restricted in a single turn"
                airborne[move.drone_id] = (origin, target, conn.name)
            else:
                assert move.arrives, "normal zone in two turns"

            on_link[conn.name] = on_link.get(conn.name, 0) + 1
            assert on_link[conn.name] <= conn.max_link_capacity, (
                f"turn {number}: {conn.name} over its capacity"
            )
            assert (target, origin, conn.name) not in directions, (
                f"turn {number}: head-on crossing on {conn.name}"
            )
            directions.add((origin, target, conn.name))

            if move.arrives:
                at[move.drone_id] = target
                if move.target is graph.end_hub:
                    delivered.add(move.drone_id)

        occupancy: Dict[str, int] = {}
        for drone_id, zone_name in at.items():
            if drone_id not in airborne:
                occupancy[zone_name] = occupancy.get(zone_name, 0) + 1
        for zone_name, count in occupancy.items():
            zone = graph.get_zone(zone_name)
            assert count <= zone.max_drones, (
                f"turn {number}: {count} drones in {zone_name}"
            )

    assert not airborne, "the simulation ended with drones in the air"
    assert delivered == set(range(1, nb_drones + 1)), "not every drone arrived"
    assert not trace or trace[-1], "the last turn must have moves"


# --- Drone ---------------------------------------------------------------

def test_new_drone_waits_at_start() -> None:
    _, graph = load("valid/linear.txt")
    assert graph.start_hub is not None
    drone = Drone(1, graph.start_hub)
    assert drone.state is DroneState.WAITING and drone.is_active
    assert drone.next_step(0) is None


def test_next_step_detects_desynchronised_path() -> None:
    _, graph = load("valid/linear.txt")
    assert graph.start_hub is not None
    drone = Drone(1, graph.start_hub)
    drone.path = [Step(graph.get_zone("waypoint1"), 5, None, 1)]
    with pytest.raises(SimulationError):
        drone.next_step(0)


# --- closing tests -------------------------------------------------------

def test_single_drone_arrives_in_one_turn() -> None:
    _, trace = simulate("valid/single_drone.txt")
    assert as_text(trace) == ["D1-goal"]


def test_linear_matches_hand_calculation() -> None:
    # D1 leaves on turn 1; D2 waits one turn (start-waypoint1 has
    # capacity 1) and follows one step behind.
    _, trace = simulate("valid/linear.txt")
    assert as_text(trace) == [
        "D1-waypoint1",
        "D1-waypoint2 D2-waypoint1",
        "D1-goal D2-waypoint2",
        "D2-goal",
    ]


def test_bottleneck_three_drones_one_at_a_time() -> None:
    nb_drones, graph = load("valid/bottleneck.txt")
    sim = Simulator(graph, nb_drones)
    trace = sim.run()
    assert as_text(trace) == [
        "D1-narrow",
        "D1-goal D2-narrow",
        "D2-goal D3-narrow",
        "D3-goal",
    ]
    assert_simulation_is_legal(graph, nb_drones, trace)


@pytest.mark.parametrize("map_file", VALID_MAPS + OFFICIAL_MAPS)
def test_result_does_not_depend_on_drone_list_order(map_file: str) -> None:
    nb_drones, graph = load(map_file)
    forward = Simulator(graph, nb_drones)
    backward = Simulator(graph, nb_drones)
    backward.drones.reverse()
    assert as_text(forward.run()) == as_text(backward.run())


def test_all_drones_end_arrived() -> None:
    sim, _ = simulate("valid/bottleneck.txt")
    assert all(d.state is DroneState.ARRIVED for d in sim.drones)
    assert all(d.current_zone is sim.graph.end_hub for d in sim.drones)


def test_restricted_transit_is_exactly_one_turn_in_the_air() -> None:
    _, trace = simulate("valid/restricted_chain.txt")
    assert as_text(trace) == [
        "D1-start-r1", "D1-r1", "D1-r1-r2", "D1-r2", "D1-goal",
    ]


def test_unreachable_goal_fails_at_turn_zero() -> None:
    content = (
        "nb_drones: 2\nstart_hub: s 0 0\nend_hub: e 2 0\n"
        "hub: wall 1 0 [zone=blocked]\n"
        "connection: s-wall\nconnection: wall-e\n"
    )
    nb_drones, graph = MapParser.parse(content)
    with pytest.raises(SimulationError, match="unreachable"):
        Simulator(graph, nb_drones)


@pytest.mark.parametrize("window", [1, 2, 3, 8])
@pytest.mark.parametrize("map_file", VALID_MAPS)
def test_invariants_hold_on_valid_maps(map_file: str, window: int) -> None:
    nb_drones, graph = load(map_file)
    trace = Simulator(graph, nb_drones, window).run()
    assert_simulation_is_legal(graph, nb_drones, trace)


@pytest.mark.parametrize("window", [2, 8])
@pytest.mark.parametrize("map_file", OFFICIAL_MAPS)
def test_invariants_hold_on_official_maps(map_file: str, window: int) -> None:
    nb_drones, graph = load(map_file)
    trace = Simulator(graph, nb_drones, window).run()
    assert_simulation_is_legal(graph, nb_drones, trace)


# --- replanning and safety limit ----------------------------------------

def test_in_transit_drone_survives_replanning_every_turn() -> None:
    # W = 2 → replans every turn, also with D1 in the air.
    nb_drones, graph = MapParser.parse(
        (MAPS_DIR / "valid" / "restricted_chain.txt").read_text()
        .replace("nb_drones: 1", "nb_drones: 3")
    )
    trace = Simulator(graph, nb_drones, window=2).run()
    assert_simulation_is_legal(graph, nb_drones, trace)


def test_exhausted_path_forces_replanning() -> None:
    sim, _ = simulate("valid/linear.txt")
    fresh = Simulator(sim.graph, 1, window=8)
    drone = fresh.drones[0]
    assert fresh._must_replan(0, [drone])       # cadence
    assert fresh._must_replan(1, [drone])       # no route
    drone.path = [Step(drone.current_zone, 2, None, 1)]
    assert not fresh._must_replan(1, [drone])   # with a route, off cadence


def test_replans_every_half_window() -> None:
    _, graph = load("valid/linear.txt")
    sim = Simulator(graph, 1, window=8)
    drone = sim.drones[0]
    drone.path = [Step(drone.current_zone, 99, None, 1)]  # never exhausted
    replans = [t for t in range(12) if sim._must_replan(t, [drone])]
    assert replans == [0, 4, 8]
    assert Simulator(graph, 1, window=1).replan_every == 1


def test_safety_limit_names_the_stuck_drones() -> None:
    nb_drones, graph = load("valid/bottleneck.txt")
    sim = Simulator(graph, nb_drones)
    sim.max_turns = 2
    with pytest.raises(SimulationError) as info:
        sim.run()
    message = str(info.value)
    assert "after 2 turns" in message
    assert "D2 (at narrow)" in message and "D3 (at start)" in message
    assert "D1" not in message


def test_safety_limit_scales_with_map() -> None:
    nb_drones, graph = load("valid/bottleneck.txt")
    sim = Simulator(graph, nb_drones)
    assert sim.max_turns == nb_drones * len(graph.zones) * 4


def test_capacity_violation_is_caught_at_the_turn_it_happens() -> None:
    nb_drones, graph = load("valid/bottleneck.txt")
    sim = Simulator(graph, nb_drones)
    for drone in sim.drones[:2]:
        drone.current_zone = graph.get_zone("narrow")
    with pytest.raises(SimulationError, match="2 drones in 'narrow'"):
        sim._verify(0, [])


def test_official_benchmarks() -> None:
    # Current result (W=8, order by id). If it changes, let it be on purpose.
    expected: Dict[str, int] = {
        "easy/01_linear_path.txt": 4,
        "easy/02_simple_fork.txt": 4,
        "easy/03_basic_capacity.txt": 4,
        "medium/01_dead_end_trap.txt": 8,
        "medium/02_circular_loop.txt": 15,
        "medium/03_priority_puzzle.txt": 7,
        "hard/01_maze_nightmare.txt": 13,
        "hard/02_capacity_hell.txt": 16,
        "hard/03_ultimate_challenge.txt": 26,
        "challenger/01_the_impossible_dream.txt": 43,
    }
    for name, turns in expected.items():
        _, trace = simulate(f"oficial_maps/{name}")
        assert len(trace) == turns, name
