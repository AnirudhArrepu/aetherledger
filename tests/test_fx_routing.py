import math
from app.fx import routing


def test_simple_route():
    # backup original graph
    orig_edges = routing.fx_graph.edges.copy()
    try:
        # construct simple graph USD -> EUR -> JPY and USD -> JPY
        routing.fx_graph.edges = {}
        routing.fx_graph.add_edge("USD", "EUR", 0.9)
        routing.fx_graph.add_edge("EUR", "JPY", 150.0)
        routing.fx_graph.add_edge("USD", "JPY", 135.0)

        res = routing.route_fx("USD", "JPY", 100)
        assert res is not None
        assert "path" in res and res["path"][0] == "USD" and res["path"][-1] == "JPY"
        # effective rate should be a positive float
        assert res["effective_rate"] > 0
        assert math.isclose(res["to_amount"], 100 * res["effective_rate"]) 
    finally:
        routing.fx_graph.edges = orig_edges


def test_arbitrage_detection():
    # Build a graph with negative cycle (arbitrage) and ensure route_fx returns None
    orig_edges = routing.fx_graph.edges.copy()
    try:
        routing.fx_graph.edges = {}
        # Rates that create a profitable cycle: A->B 2.0, B->C 2.0, C->A 0.3 => product = 1.2 (>1) -> negative cycle under -log transform
        routing.fx_graph.add_edge("A", "B", 2.0)
        routing.fx_graph.add_edge("B", "C", 2.0)
        routing.fx_graph.add_edge("C", "A", 0.3)

        res = routing.route_fx("A", "C", 10)
        # route_fx is designed to return None when it detects negative cycles
        assert res is None
    finally:
        routing.fx_graph.edges = orig_edges
