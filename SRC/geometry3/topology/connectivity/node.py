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
