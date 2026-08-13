# -*- coding: utf-8 -*-

from dataclasses import dataclass, field


@dataclass
class Project:

    # DXF
    document = None
    modelspace = None
    file_path = None

    # Geometry
    walls: list = field(default_factory=list)
    wall_pairs: list = field(default_factory=list)
    doors: list = field(default_factory=list)
    windows: list = field(default_factory=list)
    rooms: list = field(default_factory=list)

    # Graph
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    vertices: list = field(default_factory=list)
    half_edges: list = field(default_factory=list)
    wall_polygons: list = field(default_factory=list)
    faces: list = field(default_factory=list)

    # Geometry3 Mesh
    mesh: object | None = None