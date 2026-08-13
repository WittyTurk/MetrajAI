# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field

from SRC.geometry3.topology.connectivity.node import Node
from SRC.geometry3.topology.connectivity.segment import Segment


@dataclass(slots=True)
class Graph:

    nodes: dict[int, Node] = field(default_factory=dict)
    segments: dict[int, Segment] = field(default_factory=dict)
    adjacency: dict[int, list[int]] = field(default_factory=dict)

    def add_node(self, node: Node):

        self.nodes[node.id] = node

        if node.id not in self.adjacency:
            self.adjacency[node.id] = []

    def add_segment(self, segment: Segment):

        self.segments[segment.id] = segment

        if segment.start_node not in self.adjacency:
            self.adjacency[segment.start_node] = []

        if segment.end_node not in self.adjacency:
            self.adjacency[segment.end_node] = []

        if segment.id not in self.adjacency[segment.start_node]:
            self.adjacency[segment.start_node].append(segment.id)

        if segment.id not in self.adjacency[segment.end_node]:
            self.adjacency[segment.end_node].append(segment.id)

        start = self.nodes.get(segment.start_node)
        if start is not None:
            start.add_incident_segment(segment.id)

        end = self.nodes.get(segment.end_node)
        if end is not None:
            end.add_incident_segment(segment.id)
