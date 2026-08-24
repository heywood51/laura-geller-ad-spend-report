"""Recovery checks for the two-stage created-order matrix."""

from build_created_matrix import build_created_matrix


def total_cell(effect: float, lower: float, passes: bool = True) -> dict:
    return {
        "effect": effect, "lower80": lower, "upper80": effect + 20,
        "standard_error": 10, "probability_positive": 0.9,
        "passes_placebo": passes, "placebo_q_value": 0.001,
        "placebo_threshold": 5, "calibrated": False,
    }


def route_cell(effect: float, passes: bool = True) -> dict:
    return {
        "effect": effect, "raw_effect": effect, "passes_placebo": passes,
        "placebo_bias": 0, "placebo_threshold": 1, "placebo_p_value": 0.01,
        "placebo_empirical_p_value": 0.01, "placebo_q_value": 0.01,
        "placebo_runs": 50,
    }


def test_supported_total_is_conserved_and_rejected_total_is_zero() -> None:
    total = {"metadata": {"placebo_alpha": 0.01}, "views": {"Total": {"cells": {
        "Good|Total Business": total_cell(100, 50),
        "Uncertain|Total Business": total_cell(100, -5),
    }}}}
    routing = {
        "status": "routing", "warning": "test", "metadata": {},
        "channels": ["Good", "Uncertain"], "destinations": ["A", "B"],
        "views": {"Total": {"cells": {
            "Good|A": route_cell(30), "Good|B": route_cell(70),
            "Uncertain|A": route_cell(40), "Uncertain|B": route_cell(60),
        }}},
    }
    result = build_created_matrix(total, routing)
    view = result["views"]["Total"]
    assert view["cells"]["Good|A"]["effect"] == 30
    assert view["cells"]["Good|B"]["effect"] == 70
    assert sum(view["cells"][f"Good|{d}"]["effect"] for d in ["A", "B"]) == 100
    assert view["row_totals"]["Good"] == 100
    assert view["row_totals"]["Uncertain"] == 0
    assert all(view["cells"][f"Uncertain|{d}"]["effect"] == 0 for d in ["A", "B"])
    assert view["row_status"]["Uncertain"] == "unresolved_total_uncertainty"


if __name__ == "__main__":
    test_supported_total_is_conserved_and_rejected_total_is_zero()
    print("created_matrix: all recovery checks passed")
