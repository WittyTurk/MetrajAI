from dataclasses import dataclass


@dataclass
class TopologyEdge:

    id: int

    start_node: int
    end_node: int

    wall_id: int