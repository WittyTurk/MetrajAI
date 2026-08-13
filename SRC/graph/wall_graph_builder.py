# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.graph.wall_graph import WallGraph
from SRC.builders.wall_merge import WallMerge


class WallGraphBuilder:

    def __init__(self, project):

        self.project = project

    # -------------------------------------------------

    def build(self):

        graph = WallGraph()
        matcher = WallMerge(self.project)

        short_count = 0

        for wall in self.project.walls:

            print(
                "GRAPH_NODE_TEST",
                wall.id,
                round(wall.length, 1)
            )

            if wall.length < 20:

                print(
                    "SHORT",
                    wall.id,
                    round(wall.length, 1),
                    wall.start,
                    wall.end
                )

                continue

            graph.add_node(wall)

            print(
                "NODE",
                wall.id,
                "LEN=",
                round(wall.length, 1),
                "P1=",
                wall.start,
                "P2=",
                wall.end
            )

                        
        print("SHORT WALL COUNT =", short_count)

        horizontal = matcher.split_horizontal()
        vertical = matcher.split_vertical()

        horizontal = [
            w for w in horizontal
            if w.id in graph.nodes
        ]

        vertical = [
        w for w in vertical
        if w.id in graph.nodes
        ]

        print("FILTERED HORIZONTAL =", len(horizontal))
        print("FILTERED VERTICAL   =", len(vertical))

        self.connect_candidates(horizontal, graph, matcher)
        self.connect_candidates(vertical, graph, matcher)

        
        print()
        print("=" * 40)
        print("WALL GRAPH AUDIT")
        print("=" * 40)

        edge_count = sum(len(v) for v in graph.edges.values()) // 2

        print("Nodes :", len(graph.nodes))
        print("Edges :", edge_count)

        isolated = 0

        for neighbors in graph.edges.values():
            if len(neighbors) == 0:
                isolated += 1

        print("Isolated Walls :", isolated)

        print()
        print("ISOLATED WALL IDS")

        count = 0

        for wall_id in sorted(graph.edges):

            if len(graph.edges[wall_id]) == 0:

                wall = graph.nodes[wall_id]

                print(
                    wall.id,
                    "len=",
                    round(wall.length,1),
                    "p1=",
                    wall.start,
                    "p2=",
                    wall.end
                )

                
                count += 1

                if count >= 100:
                    break

   

        print()
        print("FIRST 20 WALL DEGREES")

        count = 0

        for wall_id in sorted(graph.edges):

            print(
                wall_id,
                "->",
                len(graph.edges[wall_id]),
                sorted(graph.edges[wall_id])
            )

            count += 1

            if count == 20:
                break
        return graph
    # -------------------------------------------------

    def connect_candidates(self, walls, graph: WallGraph, matcher: WallMerge):

        for i in range(len(walls)):

            wall1 = walls[i]

            for j in range(i + 1, len(walls)):

                wall2 = walls[j]

                if wall1.id in [62,64,240] or wall2.id in [62,64,240]:

                    print(
                        "CHECK",
                        wall1.id,
                        wall2.id,
                        "parallel=",
                        matcher.parallel(wall1, wall2)
                    )
                    if matcher.parallel(wall1, wall2):

                        print(
                            "LEN_DIFF",
                            abs(wall1.length - wall2.length)
                    )

                    distance = wall1.midpoint.distance_to(
                        wall2.midpoint
                    )

                    print(
                        "DIST",
                        round(distance,1)
                    )

                    print(
                        "OVERLAP",
                        matcher.overlap(wall1, wall2)
                    )
                if 62 in [wall1.id, wall2.id] or 64 in [wall1.id, wall2.id]:

                    print(
                        "YRANGE",
                        wall1.id,
                        wall1.y_range,
                        wall2.id,
                        wall2.y_range
                    )
            

                    print("----------------")


                if not matcher.parallel(wall1, wall2):
                    continue
                if wall1.id in [2,5,8,11,17,20] or wall2.id in [2,5,8,11,17,20]:
                    print(
                        "CHECK",
                        wall1.id,
                        wall2.id,
                        "LEN1=",
                        round(wall1.length,1),
                        "LEN2=",
                        round(wall2.length,1),
                        "DIST=",
                        round(
                            wall1.midpoint.distance_to(wall2.midpoint),
                            1
                        ),
                        "OVERLAP=",
                        matcher.overlap(wall1, wall2)
                    )

                # Uzunluk farkı
                if abs(wall1.length - wall2.length) > 100:
                    continue

                # Midpoint mesafesi
                distance = wall1.midpoint.distance_to(wall2.midpoint)

                if distance < 10 or distance > 600:
                    continue

                if not matcher.overlap(wall1, wall2):
                    continue
                                                              

                if wall1.id < 30 and wall2.id < 30:
                    print(
                        "MATCH",
                        wall1.id,
                        wall2.id,
                        "dist=",
                        round(distance, 1),
                        "len1=",
                        round(wall1.length, 1),
                        "len2=",
                        round(wall2.length, 1)
                    )
                if not matcher.overlap(wall1, wall2):
                    continue

                if wall1.id not in graph.nodes or wall2.id not in graph.nodes:
                    print(
                        "EDGE_TO_MISSING_NODE",
                        wall1.id,
                        wall2.id
                    )

                graph.add_edge(wall1.id, wall2.id)