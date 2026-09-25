"""Conexión bidireccional entre dos zonas."""

from fly_in.models.zone import Zone


class Connection:
    """Arista del grafo entre dos zonas.

    Guarda las `Zone` reales (no solo sus nombres) y la capacidad máxima de
    drones que pueden atravesarla a la vez.
    """

    def __init__(
        self, zone_a: Zone, zone_b: Zone, max_link_capacity: int = 1
    ) -> None:
        """Crea la conexión entre `zone_a` y `zone_b`.

        Args:
            zone_a: Primer extremo, tal como aparece en el archivo.
            zone_b: Segundo extremo, tal como aparece en el archivo.
            max_link_capacity: Drones que pueden cruzarla simultáneamente.
        """
        self.zone_a = zone_a
        self.zone_b = zone_b
        self.max_link_capacity = max_link_capacity

    def other_end(self, zone: Zone) -> Zone:
        """Devuelve el extremo opuesto a `zone` en esta conexión.

        Raises:
            ValueError: Si `zone` no es ninguno de los dos extremos.
        """
        if zone is self.zone_a:
            return self.zone_b
        if zone is self.zone_b:
            return self.zone_a
        raise ValueError(
            f"Zone '{zone.name}' is not part of this connection"
        )

    @property
    def name(self) -> str:
        """Nombre de la conexión tal como aparece en la salida (Cap. VII.5).

        Es único en el grafo: los nombres de zona no llevan guiones y las
        conexiones duplicadas se rechazan al parsear.
        """
        return f"{self.zone_a.name}-{self.zone_b.name}"

    def __repr__(self) -> str:
        """Representación legible para depurar."""
        return (
            f"Connection({self.zone_a.name!r}-{self.zone_b.name!r}, "
            f"max_link_capacity={self.max_link_capacity})"
        )
