"""Checks for the diagonal-anchored halo allocation."""

import json
from pathlib import Path

from build_balanced_matrix import build_balanced_matrix


GENERATED = Path(__file__).parent / "generated"


def total_cell(effect: float, se: float, passes: bool = True) -> dict:
    return {"effect": effect, "standard_error": se, "lower80": effect - 10,
            "upper80": effect + 10, "passes_placebo": passes}


def route_cell(effect: float, passes: bool = True) -> dict:
    return {"effect": effect, "passes_placebo": passes}


def test_diagonal_retains_remainder_and_columns_balance() -> None:
    total = {"metadata": {"measure": "orders"}, "views": {"Total": {"cells": {
        "A|Total Business": total_cell(100, 0), "B|Total Business": total_cell(100, 0),
    }}}}
    routing = {"metadata": {}, "channels": ["A", "B"], "destinations": ["A", "B", "Organic"],
               "views": {"Total": {"cells": {
                   "A|A": route_cell(20), "A|B": route_cell(30), "A|Organic": route_cell(70),
                   "B|A": route_cell(10), "B|B": route_cell(20), "B|Organic": route_cell(0, False),
               }}}}
    summary = {"scenario_relative_change": -0.2, "views": {"Total": {"orders": {
        "A": 500, "B": 500, "Organic": 500,
    }}}}
    result = build_balanced_matrix(total, routing, summary)["views"]["Total"]
    for destination in ("A", "B", "Organic"):
        assigned = sum(result["cells"][f"{s}|{destination}"]["effect"] for s in ("A", "B"))
        rec = result["column_reconciliation"][destination]
        assert abs(assigned + rec["unassigned_original_attribution"] - rec["benchmark"]) < 1e-8
    assert result["cells"]["A|A"]["kind"] == "retained_self_attribution"
    assert result["cells"]["A|B"]["kind"] == "cross_source_halo"


def test_published_balanced_outputs_reconcile() -> None:
    for measure in ("orders", "revenue"):
        model = json.loads(
            (GENERATED / f"halo-balanced-{measure}.json").read_text(encoding="utf8")
        )
        for view in model["views"].values():
            for destination, rec in view["column_reconciliation"].items():
                assigned = sum(
                    view["cells"][f"{source}|{destination}"]["effect"]
                    for source in model["channels"]
                )
                assert abs(assigned + rec["unassigned_original_attribution"] - rec["benchmark"]) < 1e-6
                assert all(
                    view["cells"][f"{source}|{destination}"]["effect"] >= 0
                    for source in model["channels"]
                )
            tv_cell = view["cells"]["Television|Television"]
            assert tv_cell["effect"] == 0
            assert tv_cell["kind"] == "structural_zero_non_addressable"


if __name__ == "__main__":
    test_diagonal_retains_remainder_and_columns_balance()
    test_published_balanced_outputs_reconcile()
    print("balanced_matrix: all accounting checks passed")
