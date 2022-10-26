from backend.dataflow.basicblock import BasicBlock
from queue import Queue
"""
CFG: Control Flow Graph

nodes: sequence of basicblock
edges: sequence of edge(u,v), which represents after block u is executed, block v may be executed
links: links[u][0] represent the Prev of u, links[u][1] represent the Succ of u,
"""


class CFG:
    def __init__(self, nodes: list[BasicBlock], edges: list[(int, int)]) -> None:
        self.nodes = nodes
        self.edges = edges

        self.links = []

        for i in range(len(nodes)):
            self.links.append((set(), set()))

        for (u, v) in edges:
            self.links[u][1].add(v)
            self.links[v][0].add(u)

        # search the graph and determine nodes reachable from the root
        self.reachable = set()
        q = Queue()
        q.put(0)
        while not q.empty():
            visited_node = q.get()
            self.reachable.add(visited_node)
            for n in self.links[visited_node][1].difference(self.reachable):
                q.put(n)

    def getBlock(self, id):
        return self.nodes[id]

    def getPrev(self, id):
        return self.links[id][0]

    def getSucc(self, id):
        return self.links[id][1]

    def getInDegree(self, id):
        return len(self.links[id][0])

    def getOutDegree(self, id):
        return len(self.links[id][1])

    def iterator(self):
        for n in self.reachable:
            yield self.nodes[n]
