"""Controlador de reproducción paso a paso (SP10.B).

Gestiona el estado de navegación: qué turno mostrar, si se está reproduciendo,
velocidad de reproducción y saltos a fotogramas específicos.
"""


class PlaybackController:
    """Controlador de reproducción de un log grabado.

    Permite navegar turno a turno, jugar/pausar, cambiar velocidad y saltar
    a posiciones específicas.
    """

    def __init__(self, total_frames: int) -> None:
        """Prepara el controlador.

        Args:
            total_frames: El número total de fotogramas (len(trace)).
        """
        self.total_frames = total_frames
        self.current_frame = 0
        self.playing = False
        self.speed_factor = 1.0

    def next(self) -> None:
        """Avanza al siguiente fotograma (si no es el último)."""
        if self.current_frame < self.total_frames - 1:
            self.current_frame += 1

    def prev(self) -> None:
        """Retrocede al fotograma anterior (si no es el primero)."""
        if self.current_frame > 0:
            self.current_frame -= 1

    def goto(self, frame: int) -> None:
        """Salta a un fotograma específico (0..total_frames-1)."""
        self.current_frame = max(0, min(frame, self.total_frames - 1))

    def home(self) -> None:
        """Salta al primer fotograma."""
        self.current_frame = 0

    def end(self) -> None:
        """Salta al último fotograma."""
        self.current_frame = self.total_frames - 1

    def toggle_play(self) -> None:
        """Cambia entre reproducción y pausa."""
        self.playing = not self.playing

    def set_speed(self, delta: float) -> None:
        """Ajusta la velocidad de reproducción.

        Args:
            delta: Cambio en la velocidad (-0.1, +0.1, etc).
                   Se limita a [0.5, 2.0].
        """
        self.speed_factor = max(0.5, min(2.0, self.speed_factor + delta))

    def advance_frames(self, count: int) -> None:
        """Salta adelante o atrás un número de fotogramas.

        Args:
            count: Número de fotogramas (positivo = adelante).
        """
        self.goto(self.current_frame + count)
