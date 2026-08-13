# -*- coding: utf-8 -*-
"""
Grid builder — duvar eksenlerinden veya AxisGrid'den.

  GridBuilder(tol=50).build(axes)
  GridBuilder().build_from_axis_grid(axis_grid)
"""

from __future__ import annotations

from typing import List, Optional, Any

from SRC.models.grid import Grid
from SRC.models.wall_component import Orientation


class GridBuilder:

    def __init__(self, tol: float = 50.0, unit_scale: float = 1.0):
        self.tol = tol
        self.unit_scale = unit_scale

    def find_group(self, coord: float, groups: dict) -> Optional[float]:
        for existing in groups.keys():
            if abs(existing - coord) <= self.tol:
                return existing
        return None

    def build(self, axes) -> List[Grid]:
        grids: List[Grid] = []
        horizontal = {}
        vertical = {}

        for axis in axes:
            if axis.orientation == Orientation.HORIZONTAL:
                coord = axis.start.y * self.unit_scale
                key = self.find_group(coord, horizontal)
                if key is None:
                    key = coord
                    horizontal[key] = []
                horizontal[key].append(axis)

            elif axis.orientation == Orientation.VERTICAL:
                coord = axis.start.x * self.unit_scale
                key = self.find_group(coord, vertical)
                if key is None:
                    key = coord
                    vertical[key] = []
                vertical[key].append(axis)

        grid_id = 1
        for key, axis_list in sorted(horizontal.items()):
            grids.append(
                Grid(
                    id=grid_id,
                    orientation=Orientation.HORIZONTAL,
                    coordinate=key,
                    axis_ids=[a.id for a in axis_list],
                )
            )
            grid_id += 1

        for key, axis_list in sorted(vertical.items()):
            grids.append(
                Grid(
                    id=grid_id,
                    orientation=Orientation.VERTICAL,
                    coordinate=key,
                    axis_ids=[a.id for a in axis_list],
                )
            )
            grid_id += 1

        print()
        print("=" * 40)
        print("GRIDS")
        print("=" * 40)
        print(f"Yatay : {sum(1 for g in grids if g.orientation == Orientation.HORIZONTAL)}")
        print(f"Düşey : {sum(1 for g in grids if g.orientation == Orientation.VERTICAL)}")
        for grid in grids:
            print(
                f"  {grid.id:3d}  {grid.orientation.name:12}  "
                f"coord={grid.coordinate:.2f}  axes={grid.axis_ids}"
            )
        return grids

    def build_from_axis_grid(self, axis_grid: Any) -> List[Grid]:
        grids: List[Grid] = []
        gid = 1
        for lab, xu in zip(axis_grid.x_labels, axis_grid.x_positions_u):
            grids.append(
                Grid(
                    id=gid,
                    orientation=Orientation.VERTICAL,
                    coordinate=xu * self.unit_scale,
                    axis_ids=[],
                )
            )
            gid += 1
        for lab, yu in zip(axis_grid.y_labels, axis_grid.y_positions_u):
            grids.append(
                Grid(
                    id=gid,
                    orientation=Orientation.HORIZONTAL,
                    coordinate=yu * self.unit_scale,
                    axis_ids=[],
                )
            )
            gid += 1

        print()
        print("=" * 40)
        print("GRIDS (AxisGrid)")
        print("=" * 40)
        print(f"X aks : {axis_grid.x_labels}  → {axis_grid.x_spacings_m}")
        print(f"Y aks : {axis_grid.y_labels}  → {axis_grid.y_spacings_m}")
        return grids