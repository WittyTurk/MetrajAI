# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.geometry3.topology.half_edge import HalfEdge
from SRC.utils.debug_logger import DebugLogger
from SRC.utils.geometry_key import GeometryKey
import math
    
class HalfEdgeBuilder:

    def __init__(self, project):

        self.project = project

    # ---------------------------------------------------------

    def assign_next(self):

        used_next = {}

        for edge in self.project.half_edges:

            next_edge = self.find_next_edge(edge)

            if next_edge is not None:

                if next_edge.id in used_next:

                    print(
                        "DUPLICATE NEXT",
                        "next=", next_edge.id,
                        "old_edge=", used_next[next_edge.id],
                        "new_edge=", edge.id
                )



            else:
                used_next[next_edge.id] = edge.id

    # ---------------------------------------------------------

    def find_next_edge(self, edge):

        mesh_edges = {
            e.id: e
            for e in self.project.half_edges
        }

        vertices = {
            v.id: v
            for v in self.project.vertices
        }

        if edge.twin is None:
            return None

        twin = mesh_edges.get(edge.twin)

        if twin is None:
            return None

        current_vertex = vertices.get(twin.origin)

        if current_vertex is None:
            return None

        candidates = []

        for edge_id in current_vertex.incident_edges:

            candidate = mesh_edges.get(edge_id)

            if candidate is None:
                continue

            # geldiğimiz kenara geri dönme
            if candidate.id == edge.twin:
                continue

            candidates.append(candidate)


        if not candidates:
            print(
                "NO CANDIDATE",
                "edge=", edge.id,
                "vertex=", current_vertex.id,
                "degree=", len(current_vertex.incident_edges)
            ) 

            return None

        if len(candidates) == 1:
            return candidates[0]


        # -------------------------------------------------
        # YÖN TABANLI SEÇİM
        # -------------------------------------------------

        def direction(e):

            start = vertices.get(e.origin)

            if start is None:
                return None

            twin_edge = mesh_edges.get(e.twin)

            if twin_edge is None:
                return None

            end = vertices.get(twin_edge.origin)

            if end is None:
                return None


            dx = end.x - start.x
            dy = end.y - start.y


            if abs(dx) > abs(dy):

                if dx > 0:
                    return "EAST"
                else:
                    return "WEST"

            else:
   
                if dy > 0:
                    return "NORTH"
                else:
                    return "SOUTH"



        current_dir = direction(edge)


        priority = {
            "EAST":  ["NORTH", "SOUTH", "EAST", "WEST"],
            "NORTH": ["WEST", "EAST", "NORTH", "SOUTH"],
            "WEST":  ["SOUTH", "NORTH", "WEST", "EAST"],
            "SOUTH": ["EAST", "WEST", "SOUTH", "NORTH"],
        }


        if current_dir is None:
            return candidates[0]


        preferred = priority[current_dir]


        for d in preferred:

            for candidate in candidates:

                if direction(candidate) == d:
                    return candidate

            print(
            "NEXT FAIL",
            edge.id,
            "vertex",
            current_vertex.id,
            "candidate count",
            len(candidates)
        )


        return candidates[0]

    # ---------------------------------------------------------

    def assign_prev(self):
        """
        Build prev pointers from next pointers.
        """

        edge_map = {
            edge.id: edge
            for edge in self.project.half_edges
        }

        for edge in self.project.half_edges:

            if edge.next is None:
                continue

            next_edge = edge_map.get(edge.next)

            if next_edge is not None:
                next_edge.prev = edge.id

    # ---------------------------------------------------------

    def validate_topology(self):
        """
        Validate topology consistency.
        """
        pass

    # ---------------------------------------------------------
    def debug_selected_walls(
             self,
             wall,
             end_key,
             start_key,
             start_vertex,
             end_vertex
        ):

        target_ids = {89, 90, 91, 99}

        if wall.id not in target_ids:
            return

        DebugLogger.item("")
        DebugLogger.item(f"MW{wall.id}")
        DebugLogger.item(
            f"Start        : ({wall.start.x:.6f}, {wall.start.y:.6f})"
        )
        DebugLogger.item(
            f"End          : ({wall.end.x:.6f}, {wall.end.y:.6f})"
        )
        DebugLogger.item(f"StartVertex  : {start_vertex.id}")
        DebugLogger.item(f"EndVertex    : {end_vertex.id}")
        DebugLogger.item(f"StartKey     : {start_key}")
        DebugLogger.item(f"EndKey       : {end_key}")

    # ---------------------------------------------------------

    def debug_origin_destination_groups(self):
        pair_groups = {}

        for wall in self.project.merged_walls:

            start_key = GeometryKey.point(wall.start)
            end_key = GeometryKey.point(wall.end)

            start_vertex = None
            end_vertex = None

            for vertex in self.project.vertices:

                vertex_key = GeometryKey.point(vertex.x, vertex.y)

                if vertex_key == start_key:
                    start_vertex = vertex

                if vertex_key == end_key:
                    end_vertex = vertex

            key = (
                start_vertex.id,
                end_vertex.id
            )

            pair_groups.setdefault(key, []).append(wall.id)

        DebugLogger.subtitle(
            "START-END VERTEX GROUPS"
        )

        duplicate_found = False

        for key, wall_ids in sorted(pair_groups.items()):

            if len(wall_ids) <= 1:
                continue

            duplicate_found = True

            DebugLogger.item(
                f"({key[0]},{key[1]})"
                f"  count={len(wall_ids)}"
                f"  walls={wall_ids}"
            )

        if not duplicate_found:
            DebugLogger.item("No duplicate start/end vertex groups")

    # ---------------------------------------------------------
    
    def diagnostic_summary(self):

        print(">>>>>>>> DIAGNOSTIC SUMMARY <<<<<<<<")
        
        edge_by_id = {
            edge.id: edge
            for edge in self.project.half_edges
        }

        vertex_by_id = {
            vertex.id: vertex
            for vertex in self.project.vertices
        }

        next_target_counts = {}
        prev_target_counts = {}
        next_missing = 0
        prev_missing = 0
        twin_missing = 0
        dangling_edge_count = 0
        missing_angle = 0

        	

        invalid_origin = 0
        invalid_twin = 0
        invalid_next = 0
        invalid_prev = 0
        missing_face = 0

        for edge in self.project.half_edges:

            if edge.origin not in vertex_by_id:
                invalid_origin += 1

            if edge.twin is None:
                twin_missing += 1
            else:
                if edge.twin not in edge_by_id:
                    invalid_twin += 1

            if edge.next is None:
                next_missing += 1
            else:
                next_target_counts[edge.next] = next_target_counts.get(edge.next, 0) + 1
                if edge.next not in edge_by_id:
                    invalid_next += 1

            if edge.prev is None:
                prev_missing += 1
            else:
                prev_target_counts[edge.prev] = prev_target_counts.get(edge.prev, 0) + 1
                if edge.prev not in edge_by_id:
                    invalid_prev += 1

            if edge.face is None:
                missing_face += 1

            if edge.angle is None:
                missing_angle += 1

            if (edge.twin is None) or (edge.next is None) or (edge.prev is None):
                dangling_edge_count += 1

        same_next_edges = 0
        for count in next_target_counts.values():
            if count > 1:
                same_next_edges += count

        same_prev_edges = 0
        for count in prev_target_counts.values():
            if count > 1:
                same_prev_edges += count

        degree1 = 0
        degree2 = 0
        degree3 = 0
        degree4 = 0
        degree5 = 0

        for vertex in self.project.vertices:

            degree = len(vertex.incident_edges)

            if degree == 1:
                degree1 += 1
            elif degree == 2:
                degree2 += 1
            elif degree == 3:
                degree3 += 1
            elif degree == 4:
                degree4 += 1
            elif degree >= 5:
                degree5 += 1

        DebugLogger.subtitle("FIRST 20 DEGREE > 2")

        count = 0

        for vertex in self.project.vertices:

            if len(vertex.incident_edges) <= 2:
                continue

            DebugLogger.item(
                f"Vertex {vertex.id} : {vertex.incident_edges}"
            )

            count += 1

            if count >= 20:
                break

        DebugLogger.subtitle("HALF EDGE DIAGNOSTIC SUMMARY")
        DebugLogger.value("Vertex", len(self.project.vertices))
        DebugLogger.value("HalfEdge", len(self.project.half_edges))
        DebugLogger.value("Invalid Origin", invalid_origin)
        DebugLogger.value("Invalid Twin Ref", invalid_twin)
        DebugLogger.value("Invalid Next Ref", invalid_next)
        DebugLogger.value("Invalid Prev Ref", invalid_prev)
        DebugLogger.value("Missing Face", missing_face)
        DebugLogger.value("Missing Angle", missing_angle)
        DebugLogger.value("Missing Next", next_missing)
        DebugLogger.value("Missing Prev", prev_missing)
        DebugLogger.value("Missing Twin", twin_missing)
        DebugLogger.value("Degree 1", degree1)
        DebugLogger.value("Degree 2", degree2)
        DebugLogger.value("Degree 3", degree3)
        DebugLogger.value("Degree 4", degree4)
        DebugLogger.value("Degree >=5", degree5)
        DebugLogger.value("Same Next Target", same_next_edges)
        DebugLogger.value("Same Prev Target", same_prev_edges)
        DebugLogger.value("Dangling Edge", dangling_edge_count)

        # ---------------------------------------------------------

        def debug_vertex_degree(self):

            mesh = self.project.mesh

            print()
            print("=" * 40)
            print("VERTEX DEGREE AUDIT")
            print("=" * 40)

            degree_count = {}

            for vertex in mesh.vertices.values():

                degree = len(vertex.incident_edges)

                degree_count[degree] = degree_count.get(degree, 0) + 1

            for degree in sorted(degree_count):
                print(f"Degree {degree}: {degree_count[degree]}")

            print()
            print("FIRST 50 DEGREE-1 VERTICES")

            shown = 0

            for vertex in mesh.vertices.values():

                if len(vertex.incident_edges) != 1:
                    continue

                edge = mesh.get_half_edge(vertex.incident_edges[0])

                print(
                    f"V{vertex.id:4} "
                    f"({vertex.x:.1f}, {vertex.y:.1f}) "
                    f"Edge={edge.id} Wall={edge.wall_id}"
                )

                shown += 1

                if shown == 50:
                    break

    

    # ---------------------------------------------------------

    def build(self):

        DebugLogger.section("HALF EDGE BUILDER")

        self.project.half_edges.clear()

        print()
        print("MERGED WALL COUNT =", len(self.project.merged_walls))

        for wall in self.project.merged_walls[:30]:
            print(
                wall.id,
                wall.start_node,
                wall.end_node,
                (wall.start.x, wall.start.y),
                (wall.end.x, wall.end.y)
            )

        # ---------------------------------------------
        # Vertex lookup
        # ---------------------------------------------

        vertex_lookup = {}

        for vertex in self.project.vertices:
            vertex_lookup[vertex.id] = vertex

        # ---------------------------------------------
        # HalfEdge uret
        # ---------------------------------------------

        DebugLogger.subtitle("SELECTED MERGED WALL DEBUG")

        edge_id = 1

        for wall in self.project.merged_walls:

            start_vertex = vertex_lookup[wall.start_node]
            end_vertex = vertex_lookup[wall.end_node]

            he1 = HalfEdge(
                id=edge_id,
                origin=start_vertex.id,
                wall_id=wall.id
            )

            he2 = HalfEdge(
                id=edge_id + 1,
                origin=end_vertex.id,
                wall_id=wall.id
            )
            # -------------------------------------------------
            # Direction angle
            # -------------------------------------------------

            dx = end_vertex.x - start_vertex.x
            dy = end_vertex.y - start_vertex.y

            angle = math.degrees(math.atan2(dy, dx))
            
            if angle < 0:
                angle += 360.0

            he1.angle = angle
            he2.angle = (angle + 180.0) % 360.0

            he1.twin = he2.id
            he2.twin = he1.id

            self.project.half_edges.append(he1)
            self.project.half_edges.append(he2)

            start_vertex.incident_edges.append(he1.id)
            start_vertex.incident_edges.append(he2.id)

            end_vertex.incident_edges.append(he1.id)
            end_vertex.incident_edges.append(he2.id)
            

            # print(
                # "INCIDENT TEST",
                # start_vertex.id,
                # start_vertex.incident_edges,
                # end_vertex.id,
                # end_vertex.incident_edges
            # )
            edge_id += 2
        
        DebugLogger.value(
            "Vertex",
            len(self.project.vertices)
        )

               


        # ---------------------------------------------

        DebugLogger.value(
            "Vertex",
            len(self.project.vertices)
        )
            

        DebugLogger.value(
            "Wall",
            len(self.project.merged_walls)
        )

        DebugLogger.value(
            "HalfEdge",
            len(self.project.half_edges)
        )

        DebugLogger.subtitle("ILK 10 HALF EDGE")

        for edge in self.project.half_edges[:10]:
            DebugLogger.item(edge)

        # self.debug_origin_destination_groups()
        # self.assign_next()
        # self.assign_prev()
        self.validate_topology()
        # self.diagnostic_summary()

        mesh = self.project.mesh

        count = 0

        print()
        print("FIRST 20 VERTEX INCIDENTS")

        for v in mesh.vertices.values():
            if v.incident_edges:
                print(v.id, v.incident_edges)
                count += 1
            if count == 20:
                break

        return self.project.half_edges
