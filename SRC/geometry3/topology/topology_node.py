from dataclasses import dataclass, field


@dataclass
class TopologyNode:

    id: int

    x: float
    y: float
    h: floay

    edge_ids: list[int] = field(default_factory=list)