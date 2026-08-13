"""
SRC/domain/surface.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .entity import Entity

if TYPE_CHECKING:
    from .room import Room


@dataclass(slots=True)
class Surface(Entity):
    """
    Base surface class.

    All architectural and structural surfaces derive from this class.

    Examples
    --------
    WallSurface
    FloorSurface
    CeilingSurface
    ColumnSurface
    BeamSurface
    ShearWallSurface
    """

    room: "Room | None" = None

    geometry: object | None = None

    openings: list[object] = field(default_factory=list)

    finish_layers: list[object] = field(default_factory=list)

    # ---------------------------------------------------------

    def add_opening(self, opening: object) -> None:
        """Add an opening."""

        if opening is None:
            raise ValueError("opening is None")

        if opening not in self.openings:
            self.openings.append(opening)
            self.touch()

    # ---------------------------------------------------------

    def remove_opening(self, opening: object) -> None:
        """Remove an opening."""

        if opening in self.openings:
            self.openings.remove(opening)
            self.touch()

    # ---------------------------------------------------------

    def clear_openings(self) -> None:
        """Remove all openings."""

        self.openings.clear()
        self.touch()

    # ---------------------------------------------------------

    def add_finish_layer(self, layer: object) -> None:
        """Add a finish layer."""

        if layer is None:
            raise ValueError("layer is None")

        self.finish_layers.append(layer)
        self.touch()

    # ---------------------------------------------------------

    def remove_finish_layer(self, layer: object) -> None:
        """Remove a finish layer."""

        if layer in self.finish_layers:
            self.finish_layers.remove(layer)
            self.touch()

    # ---------------------------------------------------------

    def clear_finish_layers(self) -> None:
        """Remove all finish layers."""

        self.finish_layers.clear()
        self.touch()

    # ---------------------------------------------------------

    @property
    def gross_area(self) -> float:
        """
        Gross surface area.

        Geometry3 will implement this later.
        """

        if self.geometry is None:
            return 0.0

        if hasattr(self.geometry, "area"):
            return float(self.geometry.area)

        return 0.0

    # ---------------------------------------------------------

    @property
    def opening_area(self) -> float:
        """
        Total opening area.
        """

        area = 0.0

        for opening in self.openings:
            if hasattr(opening, "area"):
                area += float(opening.area)

        return area

    # ---------------------------------------------------------

    @property
    def net_area(self) -> float:
        """
        Net surface area.
        """

        return self.gross_area - self.opening_area