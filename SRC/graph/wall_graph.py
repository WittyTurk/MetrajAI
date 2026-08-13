# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field

from SRC.models.wall import Wall


@dataclass
class WallGraph:

    nodes: dict[int, Wall] = field(default_factory=dict)
    edges: dict[int, set[int]] = field(default_factory=dict)

    # -------------------------------------------------

    def clear(self):

        self.nodes.clear()
        self.edges.clear()

    # -------------------------------------------------

    def add_node(self, wall: Wall):

        self.nodes[wall.id] = wall

        if wall.id not in self.edges:
            self.edges[wall.id] = set()

    # -------------------------------------------------

    def add_edge(self, wall_id_1: int, wall_id_2: int):

        if wall_id_1 not in self.edges:
            self.edges[wall_id_1] = set()

        if wall_id_2 not in self.edges:
            self.edges[wall_id_2] = set()

        self.edges[wall_id_1].add(wall_id_2)
        self.edges[wall_id_2].add(wall_id_1)
