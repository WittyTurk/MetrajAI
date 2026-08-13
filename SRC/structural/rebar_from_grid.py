# -*- coding: utf-8 -*-
"""Donatı — aks grid. include_* bayrakları ile kalem seçimi."""

from __future__ import annotations

import math
from typing import List, Optional

from SRC.structural.rebar_models import RebarLine, RebarSchedule
from SRC.structural.axis_grid import AxisGrid
from SRC.structural.models import Column, Beam


class RebarFromGrid:
    def __init__(
        self,
        grid: AxisGrid,
        columns: Optional[List[Column]] = None,
        beams: Optional[List[Beam]] = None,
        shear_walls: Optional[list] = None,
        floor: str = "GENEL",
        raft_main_dia: float = 14.0,
        raft_main_spacing_cm: float = 15.0,
        raft_dist_dia: float = 12.0,
        raft_dist_spacing_cm: float = 20.0,
        tie_section_cm: tuple = (25.0, 40.0),
        tie_long_dia: float = 14.0,
        tie_long_count: int = 4,
        tie_stirrup_dia: float = 8.0,
        tie_stirrup_spacing_cm: float = 15.0,
        ground_slab_dia: float = 12.0,
        ground_slab_spacing_cm: float = 20.0,
        ground_slab_layers: int = 1,
        col_long_dia: float = 16.0,
        col_long_count: int = 8,
        col_stirrup_dia: float = 8.0,
        col_stirrup_spacing_cm: float = 15.0,
        col_height_cm: float = 300.0,
        wall_vert_dia: float = 14.0,
        wall_vert_spacing_cm: float = 15.0,
        wall_horiz_dia: float = 12.0,
        wall_horiz_spacing_cm: float = 20.0,
        wall_height_cm: float = 300.0,
        beam_long_dia: float = 16.0,
        beam_long_count: int = 4,
        beam_stirrup_dia: float = 8.0,
        beam_stirrup_spacing_cm: float = 15.0,
        slab_main_dia: float = 10.0,
        slab_main_spacing_cm: float = 15.0,
        slab_dist_dia: float = 8.0,
        slab_dist_spacing_cm: float = 20.0,
        include_floor_slab: bool = True,
        has_parapet: bool = False,
        parapet_length_m: float = 0.0,
        parapet_height_cm: float = 100.0,
        parapet_dia: float = 10.0,
        parapet_spacing_cm: float = 20.0,
        include_raft: bool = True,
        include_tie: bool = True,
        include_ground_slab: bool = True,
        include_columns: bool = True,
        include_walls: bool = True,
        include_beams: bool = True,
        **kwargs,
    ):
        self.grid = grid
        self.columns = columns or []
        self.beams = beams or []
        self.shear_walls = shear_walls or []
        self.floor = floor
        self.raft_main_dia = raft_main_dia
        self.raft_main_spacing_cm = raft_main_spacing_cm
        self.raft_dist_dia = raft_dist_dia
        self.raft_dist_spacing_cm = raft_dist_spacing_cm
        self.tie_section_cm = tie_section_cm
        self.tie_long_dia = tie_long_dia
        self.tie_long_count = tie_long_count
        self.tie_stirrup_dia = tie_stirrup_dia
        self.tie_stirrup_spacing_cm = tie_stirrup_spacing_cm
        self.ground_slab_dia = ground_slab_dia
        self.ground_slab_spacing_cm = ground_slab_spacing_cm
        self.ground_slab_layers = ground_slab_layers
        self.col_long_dia = col_long_dia
        self.col_long_count = col_long_count
        self.col_stirrup_dia = col_stirrup_dia
        self.col_stirrup_spacing_cm = col_stirrup_spacing_cm
        self.col_height_cm = col_height_cm
        self.wall_vert_dia = wall_vert_dia
        self.wall_vert_spacing_cm = wall_vert_spacing_cm
        self.wall_horiz_dia = wall_horiz_dia
        self.wall_horiz_spacing_cm = wall_horiz_spacing_cm
        self.wall_height_cm = wall_height_cm
        self.beam_long_dia = beam_long_dia
        self.beam_long_count = beam_long_count
        self.beam_stirrup_dia = beam_stirrup_dia
        self.beam_stirrup_spacing_cm = beam_stirrup_spacing_cm
        self.slab_main_dia = slab_main_dia
        self.slab_main_spacing_cm = slab_main_spacing_cm
        self.slab_dist_dia = slab_dist_dia
        self.slab_dist_spacing_cm = slab_dist_spacing_cm
        self.include_floor_slab = include_floor_slab
        self.has_parapet = has_parapet
        self.parapet_length_m = parapet_length_m
        self.parapet_height_cm = parapet_height_cm
        self.parapet_dia = parapet_dia
        self.parapet_spacing_cm = parapet_spacing_cm
        self.include_raft = include_raft
        self.include_tie = include_tie
        self.include_ground_slab = include_ground_slab
        self.include_columns = include_columns
        self.include_walls = include_walls
        self.include_beams = include_beams

    def build(self) -> RebarSchedule:
        lines: List[RebarLine] = []
        rid = 1
        groups = []
        if self.include_raft:
            groups.append(self._raft_rebar())
        if self.include_tie:
            groups.append(self._tie_beam_rebar())
        if self.include_ground_slab:
            groups.append(self._ground_slab_rebar())
        if self.include_columns:
            groups.append(self._column_rebar())
        if self.include_walls:
            groups.append(self._shear_wall_rebar())
        if self.include_beams:
            groups.append(self._beam_rebar())
        if self.include_floor_slab:
            groups.append(self._floor_slab_rebar())
        if self.has_parapet and self.parapet_length_m > 0:
            groups.append(self._parapet_rebar())

        for group in groups:
            for ln in group:
                ln.id = rid
                lines.append(ln)
                rid += 1

        allowed = set()
        if self.include_raft:
            allowed.add("radye")
        if self.include_tie:
            allowed.add("bag_kiris")
        if self.include_ground_slab:
            allowed.add("zemin_beton")
        if self.include_columns:
            allowed.add("kolon")
        if self.include_walls:
            allowed.add("perde")
        if self.include_beams:
            allowed.add("kiris")
        if self.include_floor_slab:
            allowed.add("doseme")
        if self.has_parapet:
            allowed.add("parapet")
        lines = [ln for ln in lines if ln.element in allowed]
        for i, ln in enumerate(lines, 1):
            ln.id = i

        schedule = RebarSchedule(lines=lines)
        schedule.report()
        return schedule

    def _plan_size_m(self):
        return max(self.grid.total_x_m, 0.1), max(self.grid.total_y_m, 0.1)

    def _raft_rebar(self) -> List[RebarLine]:
        lx, ly = self._plan_size_m()
        n_x = max(1, int(math.floor((ly * 100) / self.raft_main_spacing_cm)) + 1)
        n_y = max(1, int(math.floor((lx * 100) / self.raft_dist_spacing_cm)) + 1)
        lap_x = 40 * (self.raft_main_dia / 1000.0)
        lap_y = 40 * (self.raft_dist_dia / 1000.0)
        return [
            RebarLine(0, "radye", self.raft_main_dia, lx + 2 * lap_x, n_x * 2, "TEMEL", "radye X"),
            RebarLine(0, "radye", self.raft_dist_dia, ly + 2 * lap_y, n_y * 2, "TEMEL", "radye Y"),
        ]

    def _tie_beam_rebar(self) -> List[RebarLine]:
        lines = []
        b, h = self.tie_section_cm
        st_len = 2 * ((b + h) / 100.0) * 0.9
        for yl in self.grid.y_labels:
            L = self.grid.total_x_m
            lines.append(RebarLine(0, "bag_kiris", self.tie_long_dia, L + 0.5, self.tie_long_count, "TEMEL", f"bağ KX-{yl}"))
            n_st = max(1, int(math.floor((L * 100) / self.tie_stirrup_spacing_cm)) + 1)
            lines.append(RebarLine(0, "bag_kiris", self.tie_stirrup_dia, st_len, n_st, "TEMEL", f"etriye KX-{yl}"))
        for xl in self.grid.x_labels:
            L = self.grid.total_y_m
            lines.append(RebarLine(0, "bag_kiris", self.tie_long_dia, L + 0.5, self.tie_long_count, "TEMEL", f"bağ KY-{xl}"))
            n_st = max(1, int(math.floor((L * 100) / self.tie_stirrup_spacing_cm)) + 1)
            lines.append(RebarLine(0, "bag_kiris", self.tie_stirrup_dia, st_len, n_st, "TEMEL", f"etriye KY-{xl}"))
        return lines

    def _ground_slab_rebar(self) -> List[RebarLine]:
        lx, ly = self._plan_size_m()
        n_x = max(1, int(math.floor((ly * 100) / self.ground_slab_spacing_cm)) + 1)
        n_y = max(1, int(math.floor((lx * 100) / self.ground_slab_spacing_cm)) + 1)
        layers = max(1, self.ground_slab_layers)
        return [
            RebarLine(0, "zemin_beton", self.ground_slab_dia, lx + 0.4, n_x * layers, self.floor, "zemin beton X"),
            RebarLine(0, "zemin_beton", self.ground_slab_dia, ly + 0.4, n_y * layers, self.floor, "zemin beton Y"),
        ]

    def _column_rebar(self) -> List[RebarLine]:
        n_col = len(self.columns) or (len(self.grid.x_labels) * len(self.grid.y_labels))
        H = self.col_height_cm / 100.0
        lap = 40 * (self.col_long_dia / 1000.0)
        a, b = (60.0, 40.0)
        if self.columns:
            a, b = self.columns[0].section
        st_len = 2 * ((a + b) / 100.0) * 0.9
        n_st = max(1, int(math.floor(self.col_height_cm / self.col_stirrup_spacing_cm)) + 1)
        return [
            RebarLine(0, "kolon", self.col_long_dia, H + lap, self.col_long_count * n_col, self.floor, f"{n_col} kolon boyuna"),
            RebarLine(0, "kolon", self.col_stirrup_dia, st_len, n_st * n_col, self.floor, f"{n_col} kolon etriye"),
        ]

    def _shear_wall_rebar(self) -> List[RebarLine]:
        lines = []
        H = self.wall_height_cm / 100.0
        for sw in self.shear_walls:
            L = float(getattr(sw, "length_m", 0) or 0)
            if L < 0.3:
                continue
            n_vert = max(1, int(math.floor((L * 100) / self.wall_vert_spacing_cm)) + 1)
            lines.append(RebarLine(0, "perde", self.wall_vert_dia, H + 0.5, n_vert * 2, self.floor, f"perde düşey L={L:.2f}"))
            n_horiz = max(1, int(math.floor(self.wall_height_cm / self.wall_horiz_spacing_cm)) + 1)
            lines.append(RebarLine(0, "perde", self.wall_horiz_dia, L + 0.4, n_horiz * 2, self.floor, f"perde yatay L={L:.2f}"))
        return lines

    def _beam_rebar(self) -> List[RebarLine]:
        lines = []
        if not self.beams:
            for yl in self.grid.y_labels:
                lines.extend(self._one_beam(type("B", (), {"length_m": self.grid.total_x_m, "mark": f"KX-{yl}", "section": (40.0, 60.0)})()))
            for xl in self.grid.x_labels:
                lines.extend(self._one_beam(type("B", (), {"length_m": self.grid.total_y_m, "mark": f"KY-{xl}", "section": (40.0, 60.0)})()))
            return lines
        for bm in self.beams:
            lines.extend(self._one_beam(bm))
        return lines

    def _one_beam(self, bm) -> List[RebarLine]:
        L = float(getattr(bm, "length_m", 0) or 0)
        if L < 0.3:
            return []
        mark = getattr(bm, "mark", "") or ""
        sec = getattr(bm, "section", (40.0, 60.0))
        if not sec or sec[0] <= 0:
            sec = (40.0, 60.0)
        st_len = 2 * ((sec[0] + sec[1]) / 100.0) * 0.9
        n_st = max(1, int(math.floor((L * 100) / self.beam_stirrup_spacing_cm)) + 1)
        return [
            RebarLine(0, "kiris", self.beam_long_dia, L + 0.5, self.beam_long_count, self.floor, f"kiriş boyuna {mark}", mark),
            RebarLine(0, "kiris", self.beam_stirrup_dia, st_len, n_st, self.floor, f"kiriş etriye {mark}", mark),
        ]

    def _floor_slab_rebar(self) -> List[RebarLine]:
        lx, ly = self._plan_size_m()
        n_x = max(1, int(math.floor((ly * 100) / self.slab_main_spacing_cm)) + 1)
        n_y = max(1, int(math.floor((lx * 100) / self.slab_dist_spacing_cm)) + 1)
        return [
            RebarLine(0, "doseme", self.slab_main_dia, lx + 0.4, n_x, self.floor, "kat döşeme X"),
            RebarLine(0, "doseme", self.slab_dist_dia, ly + 0.4, n_y, self.floor, "kat döşeme Y"),
        ]

    def _parapet_rebar(self) -> List[RebarLine]:
        L = self.parapet_length_m
        H = self.parapet_height_cm / 100.0
        n = max(1, int(math.floor((L * 100) / self.parapet_spacing_cm)) + 1)
        return [RebarLine(0, "parapet", self.parapet_dia, H + 0.3, n * 2, self.floor, "parapet düşey")]