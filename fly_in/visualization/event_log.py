"""The terminal event log (SP10): what happens, told turn by turn.

It goes along with the window: while the window animates turn k, the
terminal writes what happened in it. It writes to `stream` (stderr):
stdout stays reserved for the lines of the subject.

It computes nothing of the simulation: it reads the trace (the `Move`s),
the positions recorded by `ReplayRecorder` and the simulator's replans.
"""

from typing import Dict, List, Optional, Sequence, Set, TextIO

from fly_in.models.graph import Graph
from fly_in.models.zone import UNLIMITED, ZoneType
from fly_in.simulation.metrics import Metrics
from fly_in.simulation.simulator import Move, Replan
from fly_in.visualization.palette import (
    RGB,
    UI_ACCENT,
    UI_DIM,
    UI_FLIGHT,
    UI_FRAME,
    UI_GOOD,
    UI_HOT,
    UI_TEXT,
    UI_TITLE,
    UI_WARN,
    Painter,
    Palette,
)
from fly_in.visualization.recorder import Position

WIDTH = 78
MAX_LISTED = 12   # waiting drones named before summarizing


class EventLog:
    """Write the briefing, each turn and the final summary."""

    def __init__(
        self,
        graph: Graph,
        nb_drones: int,
        stream: TextIO,
        paint: Painter,
        title: str,
        window: int,
        target: Optional[int] = None,
    ) -> None:
        """Set up the log for a specific map."""
        assert graph.start_hub is not None and graph.end_hub is not None
        self.graph = graph
        self.nb_drones = nb_drones
        self.stream = stream
        self.paint = paint
        self.title = title
        self.window = window
        self.target = target
        self.goal = graph.end_hub.name
        self._delivered = 0
        self._full: Set[str] = set()

    @staticmethod
    def plural(count: int, word: str) -> str:
        """'1 drone', '3 drones'."""
        return f"{count} {word}" + ("" if count == 1 else "s")

    # --- pieces --------------------------------------------------------

    def briefing(self, view: str) -> None:
        """Mission header: map, squad, target and view."""
        p = self.paint
        bar = "━" * (WIDTH - 22)
        self._say("")
        self._say(
            p(" ▌FLY-IN▐ ", fg=(10, 12, 20), bg=UI_TITLE, bold=True)
            + p(" MISSION LOG ", fg=UI_ACCENT, bold=True)
            + p(bar, fg=UI_FRAME)
        )
        rows = [
            ("MAP", p(self.title, fg=UI_TEXT, bold=True)),
            ("SQUAD", p(
                f"{EventLog.plural(self.nb_drones, 'drone')} · "
                f"{EventLog.plural(len(self.graph.zones), 'zone')} · "
                f"{EventLog.plural(len(self.graph.connections), 'link')}",
                fg=UI_TEXT)),
            ("ENGINE", p(f"WHCA* · window {self.window}", fg=UI_TEXT)),
        ]
        if self.target is not None:
            rows.append(("PAR", p(f"{self.target} turns", fg=UI_WARN,
                                  bold=True)))
        rows.append(("VIEW", view))
        for label, value in rows:
            self._say("  " + p(f"{label:<8}", fg=UI_DIM) + value)
        self._legend()
        self._say("")

    def countdown(self, value: str) -> None:
        """One line of the countdown (3, 2, 1, GO)."""
        color = UI_GOOD if value == "GO" else UI_WARN
        self._say("  " + self.paint(f"» {value}", fg=color, bold=True))

    def turn(
        self,
        number: int,
        moves: Sequence[Move],
        positions: Dict[str, Position],
        replans: Sequence[Replan] = (),
    ) -> None:
        """The block of turn `number`."""
        p = self.paint
        line = " ".join(
            f"D{m.drone_id}-"
            + (m.target.name if m.arrives else m.connection.name)
            for m in sorted(moves, key=lambda m: m.drone_id)
        )
        head = f" ── T{number:02d} "
        room = WIDTH - len(head) - 4
        shown = line if len(line) <= room else line[: room - 1] + "…"
        rule = "─" * max(2, WIDTH - len(head) - len(shown) - 3)
        self._say(
            p(head, fg=UI_TITLE, bold=True) + p(rule, fg=UI_FRAME)
            + p(" ▸ ", fg=UI_DIM) + p(shown, fg=UI_FLIGHT)
        )
        for replan in replans:
            self._say(
                "   " + p("⟳ replan", fg=UI_ACCENT, bold=True)
                + p(f" · {EventLog.plural(replan.grounded, 'drone')} planned"
                    f" · {replan.airborne} kept in flight"
                    f" · {replan.seconds * 1000:.1f} ms", fg=UI_DIM)
            )
        for move in sorted(moves, key=lambda m: m.drone_id):
            self._say("   " + self._describe(move))
        self._holding(moves, positions)
        self._capacity_alerts(positions)

    def finish(self, metrics: Metrics, replans: int) -> None:
        """The final summary."""
        p = self.paint
        verdict = ""
        good = True
        if self.target is not None:
            good = metrics.turns <= self.target
            verdict = f" · PAR {self.target} " + ("✔" if good else "✘")
        title = f" MISSION COMPLETE · {metrics.turns} TURNS{verdict} "
        color = UI_GOOD if good else UI_WARN
        side = "═" * max(2, (WIDTH - len(title)) // 2)
        self._say("")
        self._say(p(side + title + side, fg=color, bold=True))
        self._say("  " + p(
            f"moves {metrics.total_moves} · moves/turn "
            f"{metrics.avg_moves_per_turn:.2f} · avg delivery "
            f"T{metrics.avg_turns_per_drone:.1f} · waits "
            f"{metrics.total_waits} · peak airborne {metrics.peak_airborne}",
            fg=UI_TEXT))
        self._say("  " + p(
            f"compute {metrics.seconds * 1000:.0f} ms · "
            f"{EventLog.plural(replans, 'replan')} · "
            f"{metrics.drones}/{metrics.drones} delivered · "
            "capacities verified every turn", fg=UI_DIM))
        self._say("")

    def note(self, text: str, color: RGB = UI_DIM) -> None:
        """A standalone line (notices from the view…)."""
        self._say("  " + self.paint(text, fg=color))

    def _legend(self) -> None:
        """Color legend for the drones."""
        p = self.paint
        if self.nb_drones <= 8:
            # Show every drone if there are 8 or fewer
            drones = list(range(1, self.nb_drones + 1))
            parts = [p(f"D{d}", fg=Palette.drone_color(d), bold=True)
                     for d in drones]
            self._say("  " + p("DRONES: ", fg=UI_DIM) + " ".join(parts))
        elif self.nb_drones <= 16:
            # Show every drone if there are 16 or fewer
            drones = list(range(1, self.nb_drones + 1))
            line = "  " + p("DRONES: ", fg=UI_DIM)
            for i, d in enumerate(drones):
                if i > 0:
                    line += "  "
                line += p(f"D{d}", fg=Palette.drone_color(d),
                          bold=True)
            self._say(line)
        else:
            # Show the first 8 + a summary if there are more than 16
            line = "  " + p("DRONES: ", fg=UI_DIM)
            for d in range(1, 9):
                if d > 1:
                    line += "  "
                line += p(f"D{d}", fg=Palette.drone_color(d),
                          bold=True)
            line += p(f"  +{self.nb_drones - 8} more", fg=UI_DIM)
            self._say(line)

    # --- internals -----------------------------------------------------

    def _describe(self, move: Move) -> str:
        """A move told as an event."""
        p = self.paint
        tag = p(f"D{move.drone_id:<3}", fg=Palette.drone_color(move.drone_id),
                bold=True)
        target = move.target.name
        if move.target.name == self.goal and move.arrives:
            self._delivered += 1
            filled = round(12 * self._delivered / self.nb_drones)
            bar = "█" * filled + "░" * (12 - filled)
            return (
                tag + p(f" ★ DELIVERED to {target}", fg=UI_GOOD, bold=True)
                + p(f"  {bar} {self._delivered}/{self.nb_drones}",
                    fg=UI_GOOD)
            )
        if not move.arrives:
            return tag + p(
                f" ◆ takes off → {target} via {move.connection.name}"
                " (2 turns in the air)", fg=UI_FLIGHT)
        if move.target.zone_type is ZoneType.RESTRICTED:
            return tag + p(f" ◆ lands on {target}", fg=UI_WARN)
        where = move.target.zone_type
        suffix = p("  (priority)", fg=UI_DIM) if (
            where is ZoneType.PRIORITY) else ""
        return tag + p(f" → {target}", fg=UI_TEXT) + suffix

    def _holding(
        self, moves: Sequence[Move], positions: Dict[str, Position]
    ) -> None:
        """Who stays still this turn, grouped by zone."""
        p = self.paint
        moved = {m.drone_id for m in moves}
        waiting: Dict[str, List[int]] = {}
        for key, pos in positions.items():
            drone = int(key)
            if pos[0] == "z" and drone not in moved:
                waiting.setdefault(pos[1], []).append(drone)
        for zone, ids in sorted(waiting.items()):
            ids.sort()
            names = " ".join(
                p(f"D{i}", fg=Palette.drone_color(i), bold=True)
                for i in ids[:MAX_LISTED]
            )
            if len(ids) > MAX_LISTED:
                names += p(f" … +{len(ids) - MAX_LISTED}", fg=UI_DIM)
            self._say(
                "   " + p("·    holding", fg=UI_DIM)
                + p(f" at {zone}: ", fg=UI_DIM)
                + names
            )

    def _capacity_alerts(self, positions: Dict[str, Position]) -> None:
        """Warn when a zone becomes full (only when it changes)."""
        counts: Dict[str, int] = {}
        for pos in positions.values():
            if pos[0] == "z":
                counts[pos[1]] = counts.get(pos[1], 0) + 1
        full = set()
        for name, count in counts.items():
            zone = self.graph.get_zone(name)
            if zone.max_drones != UNLIMITED and count >= zone.max_drones:
                full.add(name)
        for name in sorted(full - self._full):
            cap = int(self.graph.get_zone(name).max_drones)
            self._say(
                "   " + self.paint(f"⚠    {name} is FULL ({cap}/{cap})",
                                   fg=UI_HOT)
            )
        self._full = full

    def _say(self, text: str) -> None:
        """Write a line and flush the buffer: the log is live."""
        self.stream.write(text + "\n")
        self.stream.flush()
