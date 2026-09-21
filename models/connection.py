from models.zone import Zone


class Connection:
    """
    Arista del grafo entre dos zonas.

    Guarda las `Zone` reales (no solo sus nombres) y la capacidad máxima de
    drones simultáneos, tal como pide el diagrama de clases de
    01-arquitectura.md.
    """

    def __init__(self, zone_a: Zone, zone_b: Zone, max_link_capacity: int = 1) -> None:
        self.zone_a = zone_a
        self.zone_b = zone_b
        self.max_link_capacity = max_link_capacity

    def other_end(self, zone: Zone) -> Zone:
        """Devuelve el extremo opuesto a `zone` en esta conexión."""
        if zone is self.zone_a:
            return self.zone_b
        if zone is self.zone_b:
            return self.zone_a
        raise ValueError(
            f"Zone '{zone.name}' is not part of this connection"
        )

    @property
    def name(self) -> str:
        """Nombre de la conexión tal como aparece en la salida (Cap. VII.5)."""
        return f"{self.zone_a.name}-{self.zone_b.name}"

    def __repr__(self) -> str:
        return (
            f"Connection({self.zone_a.name!r}-{self.zone_b.name!r}, "
            f"max_link_capacity={self.max_link_capacity})"
        )
