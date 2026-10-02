"""Tests de la CLI (SP03): ningún input debe acabar en traceback."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Ejecuta `python -m fly_in.main` como lo haría el evaluador."""
    return subprocess.run(
        [sys.executable, "-m", "fly_in.main", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )


def write(tmp_path: Path, content: str) -> str:
    """Escribe un mapa temporal y devuelve su ruta."""
    path = tmp_path / "map.txt"
    path.write_text(content)
    return str(path)


def test_valid_map_succeeds() -> None:
    result = run_cli("maps/valid/linear.txt", "--quiet")
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.splitlines() == [
        "D1-waypoint1",
        "D1-waypoint2 D2-waypoint1",
        "D1-goal D2-waypoint2",
        "D2-goal",
    ]


def test_stdout_holds_only_turn_lines_even_with_visuals() -> None:
    # Sin terminal (como aquí), el renderer va en modo registro a stderr.
    result = run_cli("maps/valid/bottleneck.txt", "--metrics")
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "D1-narrow", "D1-goal D2-narrow", "D2-goal D3-narrow", "D3-goal",
    ]
    assert "MISSION COMPLETE" in result.stderr
    assert "turns: 4" in result.stderr
    assert "\033" not in result.stderr


def test_window_option_reaches_the_simulator() -> None:
    result = run_cli("maps/valid/bottleneck.txt", "--window", "1", "-q")
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == 4


@pytest.mark.parametrize("delay", ["-1", "abc", "nan"])
def test_delay_must_be_a_non_negative_number(delay: str) -> None:
    result = run_cli("maps/valid/linear.txt", "--delay", delay)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "content",
    [
        "",
        "# solo comentarios\n",
        "nb_drones: 1\nstart_hub: s 0 0\n",
        "nb_drones: 1\nstart_hub: s 0 0\nend_hub: e 1 0\nhub: x 1 1 [=]\n",
    ],
)
def test_invalid_maps_fail_cleanly(tmp_path: Path, content: str) -> None:
    result = run_cli(write(tmp_path, content))
    assert result.returncode == 1
    assert result.stderr.startswith("Error:")
    assert "Traceback" not in result.stderr


def test_unreachable_end_hub_is_reported(tmp_path: Path) -> None:
    content = (
        "nb_drones: 1\nstart_hub: s 0 0\nend_hub: e 2 0\n"
        "hub: wall 1 0 [zone=blocked]\n"
        "connection: s-wall\nconnection: wall-e\n"
    )
    result = run_cli(write(tmp_path, content))
    assert result.returncode == 1
    assert "unreachable" in result.stderr


def test_missing_file_and_directory(tmp_path: Path) -> None:
    for target in (str(tmp_path / "nope.txt"), str(tmp_path)):
        result = run_cli(target)
        assert result.returncode == 1
        assert "Traceback" not in result.stderr


def test_non_utf8_file(tmp_path: Path) -> None:
    path = tmp_path / "bin.txt"
    path.write_bytes(b"\xff\xfe\x00nb_drones")
    result = run_cli(str(path))
    assert result.returncode == 1
    assert "UTF-8" in result.stderr


@pytest.mark.parametrize("window", ["0", "-4", "abc"])
def test_window_must_be_positive(window: str) -> None:
    result = run_cli("maps/valid/linear.txt", "--window", window)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_closed_stderr_ends_cleanly() -> None:
    # `2>&1 >/dev/null | head -1`: el lector se va y escribir en stderr da
    # BrokenPipeError. Debe acabar con código 1, no con un error de Python.
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "fly_in.main", "maps/valid/linear.txt",
             "--view", "log", "--delay", "0"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=write_end, timeout=30,
        )
    finally:
        os.close(write_end)
    assert result.returncode == 1
