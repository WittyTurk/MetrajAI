# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.graph.wall_graph import WallGraph
from SRC.models.wall import Wall
from SRC.models.wall_component import Orientation
from SRC.models.wall_component import WallComponent


class WallComponentBuilder:
    """
    Connected component listesinden WallComponent üretir.
    Büyük projeler için güçlendirilmiştir.
    """

    def build(
        self,
        components: list[list[int]],
        graph: WallGraph,
    ) -> list[WallComponent]:

        result: list[WallComponent] = []

        print()
        print("=" * 50)
        print("WALL COMPONENT BUILDER")
        print("=" * 50)
        print(f"Gelen component sayısı : {len(components)}")

        skipped_empty = 0

        for index, component in enumerate(components, start=1):

            walls = self.get_component_walls(component, graph)

            # Boş component'leri atla
            if not walls:
                skipped_empty += 1
                continue

            orientation = self.resolve_orientation(walls)
            thickness = self.resolve_thickness(walls)
            total_length = sum(w.length for w in walls)

            wall_component = WallComponent(
                id=index,
                wall_ids=list(component),
                walls=walls,
                orientation=orientation,
                thickness=thickness,
            )

            # İsteğe bağlı ekstra alanlar (model destekliyorsa)
            if hasattr(wall_component, "total_length"):
                wall_component.total_length = total_length

            result.append(wall_component)

        print(f"Üretilen component     : {len(result)}")
        print(f"Atlanan (boş)          : {skipped_empty}")

        # Orientation özeti
        horz = sum(1 for c in result if c.orientation == Orientation.HORIZONTAL)
        vert = sum(1 for c in result if c.orientation == Orientation.VERTICAL)
        unk  = sum(1 for c in result if c.orientation == Orientation.UNKNOWN)
        print(f"  Horizontal : {horz}")
        print(f"  Vertical   : {vert}")
        print(f"  Unknown    : {unk}")

        return result

    # -------------------------------------------------

    def get_component_walls(
        self,
        component: list[int],
        graph: WallGraph,
    ) -> list[Wall]:

        walls: list[Wall] = []

        for wall_id in component:
            wall = graph.nodes.get(wall_id)
            if wall is not None:
                walls.append(wall)

        return walls

    # -------------------------------------------------

    def resolve_orientation(self, walls: list[Wall]) -> Orientation:
        """
        Component içindeki duvarların çoğunluk yönüne göre karar ver.
        Tek duvara bakmak yerine oylama yapar (daha sağlam).
        """
        if not walls:
            return Orientation.UNKNOWN

        h = sum(1 for w in walls if w.is_horizontal)
        v = sum(1 for w in walls if w.is_vertical)

        if h > v and h > 0:
            return Orientation.HORIZONTAL
        if v > h and v > 0:
            return Orientation.VERTICAL

        # Eşitlik veya eğik duvarlar → ilk duvarın yönüne bak
        first = walls[0]
        if first.is_horizontal:
            return Orientation.HORIZONTAL
        if first.is_vertical:
            return Orientation.VERTICAL

        return Orientation.UNKNOWN

    # -------------------------------------------------

    def resolve_thickness(self, walls: list[Wall]) -> float:
        """
        Component kalınlığı:
        - thickness > 0 olan duvarların ortalaması
        - hiçbiri yoksa 0
        """
        values = []
        for wall in walls:
            t = getattr(wall, "thickness", 0.0)
            try:
                t = float(t)
            except (TypeError, ValueError):
                continue
            if t > 0:
                values.append(t)

        if not values:
            return 0.0

        return sum(values) / len(values)