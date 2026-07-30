from typing import Dict, List, Tuple, Optional
from math import inf

class FXGraph:
    def __init__(self):
        self.edges = {}

    def add_edge(self, frm: str, to: str, rate: float):
        self.edges.setdefault(frm, []).append((to, rate))


fx_graph = FXGraph()

fx_graph.add_edge("USD", "EUR", 0.92)
fx_graph.add_edge("EUR", "JPY", 160.0)
fx_graph.add_edge("USD", "JPY", 147.0)


def _build_weighted_edges():
    from math import log

    w = []
    nodes = set()
    for frm, outs in fx_graph.edges.items():
        nodes.add(frm)
        for to, rate in outs:
            nodes.add(to)
            w.append((frm, to, -log(rate)))
    return list(nodes), w


def bellman_ford(nodes, edges, source):
    dist = {n: inf for n in nodes}
    prev = {n: None for n in nodes}
    dist[source] = 0

    for _ in range(len(nodes) - 1):
        updated = False
        for u, v, w in edges:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                prev[v] = u
                updated = True
        if not updated:
            break

    for u, v, w in edges:
        if dist[u] + w < dist[v]:
            return None, True

    return prev, False


def reconstruct_path(prev, source, target):
    path = []
    cur = target
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    if path[0] != source:
        return None
    return path


def route_fx(frm: str, to: str, amount: float) -> Optional[Dict]:
    nodes, edges = _build_weighted_edges()
    if frm not in nodes or to not in nodes:
        return None
    prev, neg_cycle = bellman_ford(nodes, edges, frm)
    if neg_cycle:
        return None
    path = reconstruct_path(prev, frm, to)
    if not path:
        return None

    effective_rate = 1.0
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i + 1]
        rate = next(r for (t, r) in fx_graph.edges[u] if t == v)
        effective_rate *= rate

    return {"path": path, "effective_rate": effective_rate, "to_amount": amount * effective_rate}
