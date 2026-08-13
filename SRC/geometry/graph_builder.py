# -*- coding: utf-8 -*-

from SRC.models.node import Node


class GraphBuilder:

    def __init__(self, project):

        self.project = project

    # -------------------------------------------------

    def merge_nodes(self):

        print()
        print("=" * 40)
        print("MERGE NODES")
        print("=" * 40)

        print(f"Önce : {len(self.project.nodes)}")

        merged = {}

        for node in self.project.nodes:

            key = (
                round(node.point.x, 3),
                round(node.point.y, 3)
            )

            if key not in merged:

                merged[key] = node

            else:

                merged[key].connected_walls.extend(
                    node.connected_walls
                )

        self.project.nodes = list(merged.values())

        print(f"Sonra : {len(self.project.nodes)}")

        print()
        print("İLK 10 NODE")
        print("-" * 40)

        for node in self.project.nodes[:10]:

            print(node)

    # -------------------------------------------------

    def build(self):

        self.project.nodes.clear()

        node_id = 1

        for wall in self.project.merged_walls:

            start_node = Node(
                id=node_id,
                point=wall.start
            )

            node_id += 1

            end_node = Node(
                id=node_id,
                point=wall.end
            )

            node_id += 1

            start_node.connected_walls.append(wall)
            end_node.connected_walls.append(wall)

            self.project.nodes.append(start_node)
            self.project.nodes.append(end_node)

        print()
        print("=" * 40)
        print("GRAPH BUILDER")
        print("=" * 40)
        print(f"MergedWall : {len(self.project.merged_walls)}")
        print(f"Node       : {len(self.project.nodes)}")

        print()
        print("İLK 5 NODE")
        print("-" * 40)

        for node in self.project.nodes[:5]:
            print(node)

        self.merge_nodes()
