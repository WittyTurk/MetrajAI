"""
SRC/domain/finish_layer.py
"""

from __future__ import annotations

from dataclasses import dataclass

from .entity import Entity


@dataclass(slots=True)
class FinishLayer(Entity):
    """
    Surface finish layer.

    Examples
    --------
    Paint
    Ceramic
    Granite
    Marble
    Epoxy
    PVC
    Plaster
    """

    code: str = ""

    description: str = ""

    material: str = ""

    start_level: float = 0.0

    end_level: float = 0.0

    thickness: float = 0.0

    # ---------------------------------------------------------

    @property
    def height(self) -> float:
        """
        Layer height.
        """

        return max(0.0, self.end_level - self.start_level)