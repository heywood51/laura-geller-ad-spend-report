"""Checks for the diagonal-anchored halo allocation."""

import json
from pathlib import Path

from build_balanced_matrix import (
    build_balanced_matrix,
    empirical_effect,
    evidence_weight,
    soft_timing_weight,
)


GENERATED = Path(__file__).parent / "generated"


def total_cell(effect: float, se: float, passes: bool = True) -> dict:
    return {"effect": effect, "standard_error": se, "lower80": effect - 10,
            "upper80": effect + 10, "passes_placebo": passes,
            "passes_lead_falsification": True, "lead_to_reference_ratio": 0.0}


def route_cell(effect: float, passes: bool = True) -> dict:
    return {"effect": effect, "standard_error": 0, "lower80": effect,
            "upper80": effect, "passes_placebo": passes,
            "passes_lead_falsification": True, "lead_to_reference_ratio": 0.0}


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
    assert result["cells"]["A|B"]["range_low"] <= result["cells"]["A|B"]["effect"]
    assert result["cells"]["A|B"]["effect"] <= result["cells"]["A|B"]["range_high"]


def test_nearby_future_signal_is_continuously_discounted() -> None:
    candidate = total_cell(100, 0)
    candidate["lead_to_reference_ratio"] = 0.9
    assert abs(evidence_weight(candidate) - 0.1) < 1e-8


def test_observational_scenario_recovers_empirical_signal_with_soft_timing() -> None:
    candidate = total_cell(0, 10, False)
    candidate.update({
        "raw_effect": 120,
        "placebo_bias": 10,
        "placebo_threshold": 20,
        "passes_empirical_null": True,
        "lead_to_reference_ratio": 1.0,
    })
    assert empirical_effect(candidate) == 90
    assert soft_timing_weight(candidate) == 0.5


def test_published_balanced_outputs_reconcile() -> None:
    for measure in ("orders", "revenue"):
        model = json.loads(
            (GENERATED / f"halo-balanced-{measure}.json").read_text(encoding="utf8")
        )
        for view in model["views"].values():
            benchmark_total = sum(
                rec["benchmark"] for rec in view["column_reconciliation"].values()
            )
            balanced_total = sum(view["row_totals"].values()) + view["unassigned_total"]
            assert abs(balanced_total - benchmark_total) < 1e-6
            for scenario in ("conservative", "central", "raw"):
                scenario_total = (
                    sum(view["scenario_row_totals"][scenario].values())
                    + view["scenario_unassigned_totals"][scenario]
                )
                assert abs(scenario_total - benchmark_total) < 1e-6
            for destination, rec in view["column_reconciliation"].items():
                assigned = sum(
                    view["cells"][f"{source}|{destination}"]["effect"]
                    for source in model["channels"]
                )
                assert abs(assigned + rec["unassigned_original_attribution"] - rec["benchmark"]) < 1e-6
                for scenario in ("conservative", "central", "raw"):
                    scenario_assigned = sum(
                        view["cells"][f"{source}|{destination}"]["scenario_effects"][scenario]
                        for source in model["channels"]
                    )
                    scenario_gap = rec["scenarios"][scenario]["unassigned_original_attribution"]
                    assert abs(scenario_assigned + scenario_gap - rec["benchmark"]) < 1e-6
                assert all(
                    view["cells"][f"{source}|{destination}"]["effect"] >= 0
                    for source in model["channels"]
                )
            tv_cell = view["cells"]["Television|Television"]
            assert tv_cell["effect"] == 0
            assert tv_cell["kind"] == "structural_zero_non_addressable"
            for source in model["channels"]:
                benchmark = view["column_reconciliation"][source]["benchmark"]
                inbound = view["column_reconciliation"][source]["cross_source_halo"]
                outbound = sum(
                    view["cells"][f"{source}|{destination}"]["effect"]
                    for destination in model["destinations"]
                    if destination != source
                )
                structural_loss = benchmark if source == "Television" else 0.0
                expected_net = outbound - inbound - structural_loss
                actual_net = view["row_totals"][source] - benchmark
                assert abs(actual_net - expected_net) < 1e-6


if __name__ == "__main__":
    test_diagonal_retains_remainder_and_columns_balance()
    test_nearby_future_signal_is_continuously_discounted()
    test_observational_scenario_recovers_empirical_signal_with_soft_timing()
    test_published_balanced_outputs_reconcile()
    print("balanced_matrix: all accounting checks passed")
