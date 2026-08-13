# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.graph.wall_graph import WallGraph


class ConnectedComponentValidator:

    def validate(self, graph: WallGraph, components: list[list[int]]) -> bool:

        component_count = len(components)

        if component_count == 0:
            largest = 0
            smallest = 0
            average = 0.0
        else:
            sizes = [len(component) for component in components]
            largest = max(sizes)
            smallest = min(sizes)
            average = sum(sizes) / component_count

        print()
        print("=" * 40)
        print("CONNECTED COMPONENTS")
        print("=" * 40)
        print()
        print(f"Component Count : {component_count}")
        print()
        print(f"Largest Component : {largest}")
        print()
        print(f"Smallest Component : {smallest}")
        print()
        print(f"Average Component Size : {average:.2f}")

        limit = min(10, component_count)

        for index in range(limit):

            component = components[index]

            print()
            print("-" * 40)
            print(f"Component {index + 1}")
            print()
            print(f"Size : {len(component)}")
            print()
            print("Walls :")
            print()

            for wall_id in component:
                print(wall_id)

            print()
            print("-" * 40)

        seen_wall_ids: set[int] = set()
        duplicate_found = False

        for component in components:
            for wall_id in component:
                if wall_id in seen_wall_ids:
                    duplicate_found = True
                    break
                seen_wall_ids.add(wall_id)
            if duplicate_found:
                break

        missing_node_found = False

        for component in components:
            for wall_id in component:
                if wall_id not in graph.nodes:
                    missing_node_found = True
                    break
            if missing_node_found:
                break

        print()

        if not duplicate_found:
            print("PASS : Her Wall yalnızca 1 component içinde.")
        else:
            print("FAIL : Aynı Wall birden fazla component içinde.")

        if not missing_node_found:
            print("PASS : Component içindeki bütün Wall ID'leri graph.nodes içinde mevcut.")
        else:
            print("FAIL : Eksik node bulundu.")

        validator_passed = (not duplicate_found) and (not missing_node_found)

        print()

        if validator_passed:
            print("CONNECTED COMPONENT VALIDATOR : PASS")
        else:
            print("CONNECTED COMPONENT VALIDATOR : FAIL")

        return validator_passed
