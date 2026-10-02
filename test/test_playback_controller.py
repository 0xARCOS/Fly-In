"""Tests del controlador de reproducción paso a paso (SP10.B)."""

from fly_in.visualization.playback_controller import PlaybackController


def test_controller_starts_at_frame_zero() -> None:
    """El controlador comienza en el fotograma 0."""
    controller = PlaybackController(10)
    assert controller.current_frame == 0
    assert not controller.playing


def test_next_advances_one_frame() -> None:
    """next() avanza un fotograma."""
    controller = PlaybackController(10)
    controller.next()
    assert controller.current_frame == 1
    controller.next()
    assert controller.current_frame == 2


def test_next_stops_at_the_last_frame() -> None:
    """next() no puede pasar el último fotograma."""
    controller = PlaybackController(5)
    for _ in range(10):  # Intentar avanzar más de lo posible
        controller.next()
    assert controller.current_frame == 4


def test_prev_goes_back_one_frame() -> None:
    """prev() retrocede un fotograma."""
    controller = PlaybackController(10)
    controller.current_frame = 5
    controller.prev()
    assert controller.current_frame == 4
    controller.prev()
    assert controller.current_frame == 3


def test_prev_stops_at_frame_zero() -> None:
    """prev() no puede pasar antes del fotograma 0."""
    controller = PlaybackController(10)
    for _ in range(10):  # Intentar retroceder demasiado
        controller.prev()
    assert controller.current_frame == 0


def test_goto_jumps_to_a_specific_frame() -> None:
    """goto() salta a un fotograma específico."""
    controller = PlaybackController(100)
    controller.goto(50)
    assert controller.current_frame == 50
    controller.goto(99)
    assert controller.current_frame == 99


def test_goto_clamps_to_valid_range() -> None:
    """goto() limita a [0, total_frames-1]."""
    controller = PlaybackController(10)
    controller.goto(-5)
    assert controller.current_frame == 0
    controller.goto(100)
    assert controller.current_frame == 9


def test_home_goes_to_the_first_frame() -> None:
    """home() salta al fotograma 0."""
    controller = PlaybackController(20)
    controller.current_frame = 15
    controller.home()
    assert controller.current_frame == 0


def test_end_goes_to_the_last_frame() -> None:
    """end() salta al último fotograma."""
    controller = PlaybackController(20)
    controller.end()
    assert controller.current_frame == 19


def test_toggle_play_changes_state() -> None:
    """toggle_play() cambia playing entre True y False."""
    controller = PlaybackController(10)
    assert not controller.playing
    controller.toggle_play()
    assert controller.playing
    controller.toggle_play()
    assert not controller.playing


def test_set_speed_adjusts_factor() -> None:
    """set_speed() ajusta la velocidad de reproducción."""
    controller = PlaybackController(10)
    assert controller.speed_factor == 1.0
    controller.set_speed(0.5)
    assert controller.speed_factor == 1.5
    controller.set_speed(-0.2)
    assert controller.speed_factor == 1.3


def test_set_speed_clamps_to_range() -> None:
    """set_speed() limita a [0.5, 2.0]."""
    controller = PlaybackController(10)
    controller.set_speed(-10.0)  # Intentar bajar demasiado
    assert controller.speed_factor == 0.5
    controller.set_speed(10.0)   # Intentar subir demasiado
    assert controller.speed_factor == 2.0


def test_advance_frames_jumps_multiple_frames() -> None:
    """advance_frames() salta un número de fotogramas."""
    controller = PlaybackController(100)
    controller.current_frame = 50
    controller.advance_frames(10)
    assert controller.current_frame == 60
    controller.advance_frames(-15)
    assert controller.current_frame == 45


def test_advance_frames_respects_boundaries() -> None:
    """advance_frames() respeta los límites."""
    controller = PlaybackController(20)
    controller.current_frame = 5
    controller.advance_frames(-20)
    assert controller.current_frame == 0
    controller.advance_frames(100)
    assert controller.current_frame == 19
