# -*- coding: utf-8 -*-

from __future__ import annotations
print("MAIN FILE LOADED")
from dataclasses import dataclass

from SRC.models.project import Project
from SRC.readers.dxf_reader import DXFReader
from SRC.builders.wall_builder import WallBuilder
from SRC.builders.merged_wall_builder_v2 import MergedWallBuilderV2
from SRC.builders.wall_axis_builder import WallAxisBuilder
from SRC.builders.wall_component_builder import WallComponentBuilder
from SRC.builders.grid_builder import GridBuilder
from SRC.geometry3.topology.vertex_builder import VertexBuilder
from SRC.geometry3.topology.half_edge_builder import HalfEdgeBuilder
from SRC.geometry3.topology.mesh import Mesh
# from SRC.geometry3.topology.next_prev_builder import NextPrevBuilder
# from SRC.geometry3.topology.next_prev_builder_v2 import NextPrevBuilderV2
from SRC.geometry3.topology.next_prev_builder_v3 import NextPrevBuilderV3
from SRC.geometry3.topology.face_builder import FaceBuilder
from SRC.geometry3.topology.room_builder import RoomBuilder
from SRC.geometry3.topology.topology_validator import ValidationError
from SRC.geometry3.topology.topology_validator import TopologyValidator
from SRC.graph.connected_component_builder import ConnectedComponentBuilder
from SRC.graph.wall_graph_builder import WallGraphBuilder
from SRC.geometry3.graph.geometry_graph_builder import GeometryGraphBuilder
from SRC.geometry3.topology.topology_graph_builder import TopologyGraphBuilder
from SRC.geometry3.topology.intersection_splitter import IntersectionSplitter
from SRC.geometry3.topology.topology_node_builder import TopologyNodeBuilder
from SRC.geometry3.topology.topology_edge_builder import TopologyEdgeBuilder
from SRC.builders.axis_detector import AxisDetector


@dataclass(slots=True)
class FacePolygon:

    id: int
    face_id: int
    points: list
    corners: list
    area: float


def _prepare_mesh(project: Project):

    project.mesh.clear()

    for vertex in project.vertices:
        project.mesh.add_vertex(vertex)

    for edge in project.half_edges:
        project.mesh.add_half_edge(edge)


def _polygon_area(points) -> float:

    if len(points) < 3:
        return 0.0

    cross_sum = 0.0

    for index in range(len(points)):
        x1, y1 = points[index].x, points[index].y
        x2, y2 = points[(index + 1) % len(points)].x, points[(index + 1) % len(points)].y
        cross_sum += (x1 * y2) - (x2 * y1)

    return abs(0.5 * cross_sum)


def _attach_polygon_area(project: Project):

    for polygon in project.wall_polygons:

        if getattr(polygon, "area", None) is not None:
            continue

        corners = getattr(polygon, "corners", None)

        if not corners:
            polygon.area = 0.0
            continue

        polygon.area = _polygon_area(corners)


def _build_face_polygons(project: Project):

    polygons = []
    small_area_diagnostics = []

    for face in project.mesh.faces.values():

        points = []

        for edge_id in face.edge_ids:

            edge = project.mesh.get_half_edge(edge_id)
            if edge is None:
                points = []
                break

            vertex = project.mesh.get_vertex(edge.origin)
            if vertex is None:
                points = []
                break

            points.append(vertex)

        if points and len(points) >= 2 and points[0] == points[-1]:
            points = points[:-1]

        area = _polygon_area(points) if len(points) >= 3 else 0.0

        polygons.append(
            FacePolygon(
                id=face.id,
                face_id=face.id,
                points=points,
                corners=points,
                area=area,
            )
        )

        if area < 1e-8 and len(small_area_diagnostics) < 10:

            unique_coordinates = {
                (float(vertex.x), float(vertex.y))
                for vertex in points
            }

            first_15_coordinates = [
                (float(vertex.x), float(vertex.y))
                for vertex in points[:15]
            ]

            small_area_diagnostics.append(
                {
                    "face_id": face.id,
                    "polygon_id": face.id,
                    "vertex_count": len(points),
                    "unique_vertex_count": len(unique_coordinates),
                    "area": area,
                    "coordinates": first_15_coordinates,
                }
            )

    project.polygons = polygons
    project.wall_polygons.clear()

    if small_area_diagnostics:

        print()
        print("POLYGON DIAGNOSTIC")

        for item in small_area_diagnostics:

            print()
            print(f"Face {item['face_id']}")
            print()
            print(f"Polygon ID: {item['polygon_id']}")
            print()
            print(f"Vertices: {item['vertex_count']}")
            print()
            print(f"Unique: {item['unique_vertex_count']}")
            print()
            print(f"Area: {item['area']}")
            print()

            for x, y in item["coordinates"]:
                print(f"({x},{y})")

    return polygons


def main():

    print("### MAIN STARTED ###")

    print("=" * 40)
    print("MetrajAI V3")

    print("=" * 40)
    print("MetrajAI V3")
    print("=" * 40)

    project = Project()

    # 1) DXF Reader
    reader = DXFReader(project)
    reader.read()

        # 2) WallBuilder

    

    WallBuilder(project).build()

    # Half-edge iskeleti (next/prev henüz yok)
    from SRC.geometry3.topology.half_edge_from_walls import HalfEdgeFromWalls
    he = HalfEdgeFromWalls(project, snap_tol=1.0)
    vertices, half_edges = he.build()

    # Aks tespiti (varsa)
    from SRC.builders.axis_detector import AxisDetector
    x_axes, y_axes = AxisDetector(project).detect()

    # Özet
    print()
    print("=" * 50)
    print("METRAJ ÖZETİ")
    print("=" * 50)
    total = sum(w.length for w in project.walls)
    print(f"Duvar adedi           : {len(project.walls)}")
    print(f"Toplam duvar uzunluğu : {total:.1f}")
    print(f"Vertex                : {len(vertices)}")
    print(f"HalfEdge              : {len(half_edges)}")

    return project

    # Şimdilik sadece duvar metrajı ile ilgileniyoruz
    print()
    print("=" * 40)
    print("DUVAR METRAJ ÖZETİ")
    print("=" * 40)
    total = sum(w.length for w in project.walls)
    print(f"Toplam Duvar Uzunluğu : {total:.1f} mm  ({total/1000:.3f} m)")
    print(f"Duvar Adedi           : {len(project.walls)}")
    for w in project.walls:
        print(f"  Wall {w.id:2d}  L={w.length:7.1f} mm  T={w.thickness:5.1f} mm")

    # --- AKS TEST ---
    from SRC.builders.axis_detector import AxisDetector
    AxisDetector(project).detect() 
  
    return project

    for wall in project.walls:

        if wall.length > 3000:

            print(
                wall.id,
                "start=(",
                round(wall.start.x,1),
                round(wall.start.y,1),
                ")",
                "end=(",
                round(wall.end.x,1),
                round(wall.end.y,1),
                ")",
                "mid=(",
                round(wall.midpoint.x,1),
                round(wall.midpoint.y,1),
                ")"
            )

    print()
    print("=" * 40)
    print("WALL LENGTH AUDIT")
    print("=" * 40)

    print("PROJECT WALL COUNT =", len(project.walls))

    if len(project.walls) == 0:
        print("NO WALLS FOUND")
    else:

        lengths = [w.length for w in project.walls]

        print("Wall Count :", len(lengths))
        print("Max Length :", round(max(lengths), 1))
        print("Average    :", round(sum(lengths) / len(lengths), 1))

        long_count = sum(1 for x in lengths if x > 1000)
        print(">1000 mm :", long_count)

        long_count = sum(1 for x in lengths if x > 3000)
        print(">3000 mm :", long_count)

    print()
    print("LAYERS")

    layers = set()

    for e in project.modelspace:
        layers.add(e.dxf.layer)

    for layer in sorted(layers):
        print(layer)

       

    print()
    print("WALL 816-838 DETAILS")
    print()
    print("AKS LINE DETAILS")

    count = 0

    for e in project.modelspace:

        if e.dxf.layer == "AKS" and e.dxftype() == "LINE":

            print(
                "start=(",
                round(e.dxf.start.x,1),
                round(e.dxf.start.y,1),
                ") end=(",
                round(e.dxf.end.x,1),
                round(e.dxf.end.y,1),
                ")"
            )

            count += 1

    print()
    print("AKS ENTITY COUNT =", count)

    print()
    print("AKS LINE COORDINATES")

    for e in project.modelspace:

        if e.dxf.layer == "AKS" and e.dxftype() == "LINE":

            print(
                "LINE",
                round(e.dxf.start.x,1),
                round(e.dxf.start.y,1),
                round(e.dxf.end.x,1),
                round(e.dxf.end.y,1)
            )

    
      

    for wall in project.walls:

        if wall.id in [
            816,817,824,825,826,828,
            829,831,832,833,834,
            836,837,838
        ]:

            print(
                wall.id,
                "start=(",
                round(wall.start.x,1),
                round(wall.start.y,1),
                ") end=(",
                round(wall.end.x,1),
                round(wall.end.y,1),
                ")"
            )

    print()
    column_x = []

    column_y = []
    print("COLUMN CENTERS")

    count = 0

    for e in project.modelspace:

        if e.dxf.layer.upper() != "KOLON":
            continue

        if e.dxftype() != "LWPOLYLINE":
            continue

        pts = list(e.get_points())

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]

        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2

        column_x.append(round(cx,1))
        column_y.append(round(cy,1))


        print(
            round(cx,1),
            round(cy,1)
        )

        count += 1

    print()
    print("COLUMN COUNT =", len(column_x))

        
    print()
    print("UNIQUE COLUMN X")

    for x in sorted(set(column_x)):
        print(x)

    print()
    print("UNIQUE COLUMN Y")

    for y in sorted(set(column_y)):
        print(y)


    from collections import Counter

    print()
    print("COLUMN X FREQUENCY")

    for x, n in Counter(column_x).most_common():
        print(x, n)

    print()
    print("MAIN COLUMN X")

    for x, n in Counter(column_x).most_common():

        if n >= 2:
            print(x, n)

    print()
    print("MAIN COLUMN Y")

    for y, n in Counter(column_y).most_common():

        if n >= 2:
            print(y, n)

    print()
    print("COLUMN Y FREQUENCY")

    for y, n in Counter(column_y).most_common():
        print(y, n)

    print()
    print("AKS LINE LENGTHS")

    count = 0

    for e in project.modelspace:

        if e.dxf.layer != "AKS":
            continue

        if e.dxftype() != "LINE":
            continue

        dx = e.dxf.end.x - e.dxf.start.x
        dy = e.dxf.end.y - e.dxf.start.y

        length = (dx * dx + dy * dy) ** 0.5

        print(round(length,1))

        count += 1

        if count >= 50:
            break

    AxisDetector(project).detect()

    # 3) WallAxisBuilder (via graph + component preparation)
    graph = WallGraphBuilder(project).build()
    components = ConnectedComponentBuilder().build(graph)
    print()
    print("=" * 40)
    print("CONNECTED COMPONENTS")
    print("=" * 40)
    
    print("COUNT =", len(components))

    for i, comp in enumerate(components[:30], start=1):
        print(i, len(comp), comp)
    wall_components = WallComponentBuilder().build(components, graph)
    
    axes = WallAxisBuilder().build(wall_components)
    grids = GridBuilder().build(axes)

    print()
    print("=" * 40)
    print("GRIDS")
    print("=" * 40)

    for grid in grids:
        print(grid)

    print("\nFIRST 20 AXES")

    for axis in axes[:20]:
        print(
            axis.id,
            f"({axis.start.x:.1f}, {axis.start.y:.1f})",
            "->",
            f"({axis.end.x:.1f}, {axis.end.y:.1f})"
        )

    print("END AXES\n")

    project.merged_walls = MergedWallBuilderV2().build(axes)

    project.merged_walls = IntersectionSplitter(project).build()

    print()
    print("=" * 40)
    print("GEOMETRY3 GRAPH")
    print("=" * 40)

    geometry_graph = GeometryGraphBuilder(project).build()

    geometry_graph.debug_print()
        
    targets = {
        (-5023.979380, -1328.289084),
        (-5023.979380, -1308.289085),
        (-398.104380, -1328.289085),
        (-398.104380, -1308.289084),
        (5812.770620, -1308.289085),
        (6212.770620, -1308.289084),
    }

    print()
    print("=" * 40)
    print("TARGET WALLS")
    print("=" * 40)

    for wall in project.merged_walls:

        start = (
            round(wall.start.x, 6),
            round(wall.start.y, 6)
        )

        end = (
            round(wall.end.x, 6),
            round(wall.end.y, 6)
        )

        if start in targets or end in targets:
            print(
                f"Wall {wall.id}: "
                f"{start} -> {end}"
            )

    print("A1")

    topology_graph = TopologyGraphBuilder(project).build()

    print("A2")

    project.topology_graph = topology_graph

    degree = {}

    for edge in topology_graph.edges.values():

        degree[edge.start_node] = degree.get(edge.start_node, 0) + 1
        degree[edge.end_node] = degree.get(edge.end_node, 0) + 1

    deg1 = sum(1 for d in degree.values() if d == 1)
    deg2 = sum(1 for d in degree.values() if d == 2)
    deg3 = sum(1 for d in degree.values() if d >= 3)

    print()
    print("DEGREE ANALYSIS")
    print("Degree=1 :", deg1)
    print("Degree=2 :", deg2)
    print("Degree>=3:", deg3)

    print("A3")

    VertexBuilder(project).build()

    print("A4")

    mesh = Mesh()

    project.mesh = mesh

    for vertex in project.vertices:
        mesh.add_vertex(vertex)

    HalfEdgeBuilder(project).build()

    print()
    print("TOPOLOGY GRAPH")
    print("Node Count :", topology_graph.node_count)
    print("XXXXXXXXXX")
   
    topology_points = {
        (round(n.x, 6), round(n.y, 6))
        for n in project.topology_graph.nodes.values()
    }

    vertex_points = {
        (round(v.x, 6), round(v.y, 6))
        for v in project.vertices
    }

    print()
    print("=" * 40)
    print("TOPOLOGY / VERTEX DIFF")
    print("=" * 40)

    print("Only in Vertex :", len(vertex_points - topology_points))

    count = 0
    for p in sorted(vertex_points - topology_points):
        print(" V+", p)
        count += 1

        if count >= 20:
            print("...")
            break

    print("Only in Topology :", len(topology_points - vertex_points))

    count = 0

    for p in sorted(topology_points - vertex_points):

        print(" T+", p)

        count += 1

        if count >= 20:
            print("...")
            break

    # 4) HalfEdgeBuilder

    print("AAAA")

    _prepare_mesh(project)

    print("BBBB")

    print(">>> BEFORE NEXTPREV <<<")

    obj = NextPrevBuilderV3(project)

    print("BEFORE OBJ BUILD")

    obj.build()

    print("AFTER OBJ BUILD")

    total = 0
    has_next = 0
    has_prev = 0

    for e in project.mesh.half_edges.values():

        total += 1

        if e.next is not None:
            has_next += 1

        if e.prev is not None:
            has_prev += 1


    print("TOTAL HALF EDGES :", total)
    print("HAS NEXT :", has_next)
    print("HAS PREV :", has_prev)

    missing_next = 0
    missing_prev = 0

    for e in project.mesh.half_edges.values():

        if e.next is None:
            missing_next += 1

            print(
                "OPEN NEXT",
                "edge=", e.id,
                "origin=", e.origin,
                "twin=", e.twin
            )

        if e.prev is None:
            missing_prev += 1


    print("MISSING NEXT :", missing_next)
    print("MISSING PREV :", missing_prev)



    total = 0
    has_next = 0
    has_prev = 0

    for e in project.mesh.half_edges.values():

        total += 1

        if e.next is not None:
            has_next += 1

        if e.prev is not None:
            has_prev += 1


    print("TOTAL HALF EDGES :", total)
    print("HAS NEXT :", has_next)
    print("HAS PREV :", has_prev) 


    

    print("DDDD")

    print()
    print("CHECK NEXT PREV")
    

    missing_next = 0
    missing_prev = 0

    for e in project.mesh.half_edges.values():

        if e.next is None:
            missing_next += 1

        if e.prev is None:
            missing_prev += 1
            print(
                "MISSING PREV",
                "edge=", e.id,
                "origin=", e.origin,
                "next=", e.next,
                "twin=", e.twin
            )
    
    print("Missing next :", missing_next)
    print("Missing prev :", missing_prev)
    print()
    print("MISSING PREV AFTER BUILD")

    missing_prev_after = 0

    for e in project.mesh.half_edges.values():

        if e.prev is None:

            print(
                "MISSING PREV AFTER BUILD",
                "edge=", e.id,
                "next=", e.next,
                "twin=", e.twin
            )

            missing_prev_after += 1


    print("MISSING PREV TOTAL =", missing_prev_after)

    print("DDDD")

    print()
    print("BUILDING FACES")

    face_builder = FaceBuilder(project)

    faces = face_builder.build()

    print("TOTAL FACES =", len(faces))

    print(">>> AFTER NEXTPREV <<<")
    

    
    # 6) TopologyValidator
    try:
        TopologyValidator(project).validate()
    except ValidationError as error:
        print()
        print(str(error))
        return project

    # 7) PolygonBuilder (FaceBuilder output -> Polygon)
    _build_face_polygons(project)

    # 8) RoomBuilder
    RoomBuilder(project).build()

    # 9) Project.rooms
    print()
    print("=" * 40)
    print("PIPELINE SUMMARY")
    print("=" * 40)
    print(f"Wall Count      : {len(project.walls)}")
    print(f"HalfEdge Count  : {len(project.mesh.half_edges)}")
    print(f"Face Count      : {len(project.mesh.faces)}")
    print(f"Polygon Count   : {len(getattr(project, 'polygons', []))}")
    print(f"Room Count      : {len(project.rooms)}")

    print()
    print("DXF OK")
    print(f"Dosya : {reader.file_path.name}")
    print(f"Entity Sayısı : {len(project.modelspace)}")
    print()
    print("=" * 40)
    print("ENTITY TİPLERİ")
    print("=" * 40)

    for name, count in reader.entity_statistics().items():
        print(f"{name:15} : {count:,}")

    print()
    print("=" * 40)
    print("LAYER LİSTESİ")
    print("=" * 40)

    for name, count in reader.layer_statistics().items():
        print(f"{name:35} : {count:,}")

    return project


    # -------------------------------------------------

    if __name__ == "__main__":
        print("ENTERING MAIN")
        main()
        print("MAIN FINISHED")
