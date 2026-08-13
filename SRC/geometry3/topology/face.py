# -*- coding: utf-8 -*-

from dataclasses import dataclass, field


@dataclass
class Face:

    id: int

    edge_ids: list[int] = field(default_factory=list)

    outer: bool = False

    area: float = 0.0

    visited: bool = False
