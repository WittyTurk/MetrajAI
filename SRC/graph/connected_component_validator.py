# -*- coding: utf-8 -*-

from __future__ import annotations


class ConnectedComponentValidator:

    def validate(self, components: list[list[int]]):

        count = len(components)

        if count == 0:
            largest = 0
            smallest = 0
            average = 0.0
        else:
            sizes = [len(component) for component in components]
            largest = max(sizes)
            smallest = min(sizes)
            average = sum(sizes) / count

        print()
        print("CONNECTED COMPONENTS")
        print()
        print(f"Component Count : {count}")
        print()
        print(f"Largest Component : {largest}")
        print()
        print(f"Smallest Component : {smallest}")
        print()
        print(f"Average Size : {average:.2f}")

        limit = min(10, count)

        for index in range(limit):

            component = components[index]
            walls = sorted(component)

            print()
            print(f"Component {index + 1}")
            print(f"Size : {len(component)}")
            print(f"Walls : {walls}")
