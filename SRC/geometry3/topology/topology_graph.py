class TopologyGraph:

    def __init__(self):

        self.nodes = {}
        self.edges = {}

    def add_node(self, node):

        self.nodes[node.id] = node

    def add_edge(self, edge):

        self.edges[edge.id] = edge

    @property
    def node_count(self):

        return len(self.nodes)

    @property
    def edge_count(self):

        return len(self.edges)