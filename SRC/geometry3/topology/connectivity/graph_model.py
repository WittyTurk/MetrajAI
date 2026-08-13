# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Node:

    id: int
    x: float
    y: float
    incident_segments: list[int] = field(default_factory=list)

    def add_incident_segment(self, segment_id: int):

        if segment_id not in self.incident_segments:
            self.incident_segments.append(segment_id)


@dataclass(slots=True)
class Segment:

    id: int
    start_node: int
    end_node: int
    source_wall_id: int | None


@dataclass(slots=True)
class Graph:

    nodes: dict[int, Node] = field(default_factory=dict)
    segments: dict[int, Segment] = field(default_factory=dict)

    def add_node(self, node: Node):

        self.nodes[node.id] = node

    def add_segment(self, segment: Segment):

        self.segments[segment.id] = segment

        start_node = self.nodes.get(segment.start_node)
        if start_node is not None:
            start_node.add_incident_segment(segment.id)

        end_node = self.nodes.get(segment.end_node)
        if end_node is not None:
            end_node.add_incident_segment(segment.id)

    @property
    def node_count(self) -> int:

        return len(self.nodes)

    @property
    def segment_count(self) -> int:

        return len(self.segments)
