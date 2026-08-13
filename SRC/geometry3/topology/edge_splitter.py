# -*- coding: utf-8 -*-
"""
Geometry3

Edge Splitter
"""

from __future__ import annotations

from math import sqrt


class EdgeSplitter:
    """
    Bir edge üzerinde bulunan node'ları tespit eder
    ve edge'i daha küçük edge'lere böler.

    V1:
        Sadece altyapıyı oluşturur.
    """

    def __init__(self, graph):

        self.graph = graph

    # ---------------------------------------------------------

    def point_on_edge(
        self,
        node,
        edge,
        tolerance=1e-6
    ):
        """
        Node, edge üzerinde mi?

        Başlangıç ve bitiş noktaları hariç tutulur.
        """

        n1 = self.graph.get_node(edge.start_node)
        n2 = self.graph.get_node(edge.end_node)

        ax = n1.x
        ay = n1.y

        bx = n2.x
        by = n2.y

        px = node.x
        py = node.y

        # -------------------------------
        # Aynı nokta mı?
        # -------------------------------

        if (
            abs(px - ax) < tolerance and
            abs(py - ay) < tolerance
        ):
            return False

        if (
            abs(px - bx) < tolerance and
            abs(py - by) < tolerance
        ):
            return False

        # -------------------------------
        # Cross Product
        # -------------------------------

        cross = (
            (px - ax) * (by - ay)
            -
            (py - ay) * (bx - ax)
        )

        if abs(cross) > tolerance:
            return False

        # -------------------------------
        # Dot Product
        # -------------------------------

        dot = (
            (px - ax) * (bx - ax)
            +
            (py - ay) * (by - ay)
        )

        if dot < 0:
            return False

        length2 = (
            (bx - ax) ** 2 +
            (by - ay) ** 2
        )

        if dot > length2:
            return False

        return True

    # ---------------------------------------------------------

    def split(self):

        print()
        print("=" * 40)
        print("EDGE SPLITTER")
        print("=" * 40)

        print(f"Node : {self.graph.node_count}")
        print(f"Edge : {self.graph.edge_count}")

        split_count = 0

        print()
        print("İLK 10 EDGE TEST")
        print("-" * 40)

        count = 0

        for edge in self.graph.edges.values():

            for node in self.graph.nodes.values():

                if self.point_on_edge(node, edge):

                    print(
                        f"Edge {edge.id} -> Node {node.id}"
                    )

                    count += 1

                    if count == 10:
                        break

            if count == 10:
                break

        print()
        print("Toplam Bulunan :", count)

        # V2 burada gerçek algoritma gelecek

        print()
        print(f"Split Edge : {split_count}")

        return split_count
