from SRC.geometry3.spatial.point_index import PointIndex

index = PointIndex(1.0)

points = [
    (1000.0, 500.0),
    (1000.2, 500.1),
    (1001.1, 500.0),
    (2500.0, 1800.0),
    (2500.0, 1800.0),
]

for x, y in points:
    node = index.get_or_create_node(x, y)
    print(node.id, node.x, node.y)

print()
index.debug_print()