"""Gate attribution routing behind supported total-business incrementality."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_created_matrix(total_model: dict, routing_model: dict) -> dict:
    result = json.loads(json.dumps(routing_model))
    result["status"] = "two_stage_placebo_and_lead_adjusted_observational"
    result["warning"] = (
        "Destination effects are published only when the source-to-total-business effect "
        "and the positive destination-routing effect both survive empirical-null correction "
        "and directed future-exposure falsification."
    )
    result["metadata"]["method"] = (
        "source-level total-business incrementality gate followed by positive destination routing; "
        "both layers require empirical-null and future-exposure lead checks"
    )
    result["metadata"]["incrementality_model"] = "source-to-total-business"
    result["metadata"]["routing_model"] = "conditional positive attribution routing"
    result["metadata"]["placebo_alpha"] = total_model["metadata"]["placebo_alpha"]

    for view_name, view in result["views"].items():
        total_view = total_model["views"][view_name]
        row_totals = {}
        row_status = {}
        for source in result["channels"]:
            total_cell = total_view["cells"][f"{source}|Total Business"]
            total_effect = float(total_cell["effect"])
            total_passes = bool(
                total_cell["passes_placebo"]
                and total_effect > 0
                and total_cell["lower80"] > 0
            )
            routing = []
            for destination in result["destinations"]:
                route_cell = view["cells"][f"{source}|{destination}"]
                route_effect = float(route_cell["effect"])
                route_passes = bool(route_cell["passes_placebo"] and route_effect > 0)
                if route_passes:
                    routing.append((destination, route_effect))
            routing_sum = sum(value for _, value in routing)
            allocatable = total_passes and routing_sum > 0
            if total_effect < 0 and total_cell["passes_placebo"]:
                status = "test_counterintuitive"
            elif not total_cell["passes_placebo"]:
                status = "no_total_incrementality_evidence"
            elif total_cell["lower80"] <= 0:
                status = "unresolved_total_uncertainty"
            elif total_effect <= 0:
                status = "unresolved_total_effect"
            elif not routing:
                status = "incremental_total_routing_unresolved"
            else:
                status = "incremental_and_routed"

            for destination in result["destinations"]:
                key = f"{source}|{destination}"
                old = view["cells"][key]
                route_effect = float(old["effect"])
                route_passes = bool(old["passes_placebo"] and route_effect > 0)
                weight = route_effect / routing_sum if allocatable and route_passes else 0.0
                effect = total_effect * weight if weight else 0.0
                view["cells"][key] = {
                    "effect": effect,
                    "lower80": max(0.0, float(total_cell["lower80"])) * weight,
                    "upper80": max(0.0, float(total_cell["upper80"])) * weight,
                    "standard_error": float(total_cell["standard_error"]) * weight,
                    "probability_positive": float(total_cell["probability_positive"]),
                    "raw_effect": float(old["raw_effect"]),
                    "routing_effect": route_effect,
                    "routing_weight": weight,
                    "routing_passes": route_passes,
                    "incrementality_effect": total_effect,
                    "incrementality_lower80": float(total_cell["lower80"]),
                    "incrementality_upper80": float(total_cell["upper80"]),
                    "incrementality_passes": bool(total_cell["passes_placebo"]),
                    "incrementality_passes_empirical_null": bool(total_cell.get("passes_empirical_null", total_cell["passes_placebo"])),
                    "incrementality_passes_lead_falsification": bool(total_cell.get("passes_lead_falsification", False)),
                    "incrementality_lead_effects": total_cell.get("lead_effects", {}),
                    "incrementality_lead_to_reference_ratio": float(total_cell.get("lead_to_reference_ratio", 0.0)),
                    "incrementality_q_value": float(total_cell["placebo_q_value"]),
                    "incrementality_placebo_threshold": float(total_cell["placebo_threshold"]),
                    "passes_placebo": bool(weight > 0),
                    "publishable": bool(weight > 0),
                    "placebo_adjusted": True,
                    "calibrated": bool(total_cell.get("calibrated", False)),
                    "row_status": status,
                    "placebo_bias": float(old["placebo_bias"]),
                    "placebo_threshold": float(old["placebo_threshold"]),
                    "placebo_p_value": float(old["placebo_p_value"]),
                    "placebo_empirical_p_value": float(old["placebo_empirical_p_value"]),
                    "placebo_q_value": float(old["placebo_q_value"]),
                    "placebo_runs": int(old["placebo_runs"]),
                    "routing_passes_empirical_null": bool(old.get("passes_empirical_null", old["passes_placebo"])),
                    "routing_passes_lead_falsification": bool(old.get("passes_lead_falsification", False)),
                    "routing_lead_effects": old.get("lead_effects", {}),
                    "routing_lead_to_reference_ratio": float(old.get("lead_to_reference_ratio", 0.0)),
                }
            row_totals[source] = total_effect if allocatable else 0.0
            row_status[source] = status
        view["row_totals"] = row_totals
        view["row_status"] = row_status
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incrementality", required=True)
    parser.add_argument("--routing", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with open(args.incrementality, encoding="utf8") as handle:
        total_model = json.load(handle)
    with open(args.routing, encoding="utf8") as handle:
        routing_model = json.load(handle)
    result = build_created_matrix(total_model, routing_model)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf8")
    print(json.dumps({
        view: {
            "routed_rows": sum(status == "incremental_and_routed" for status in data["row_status"].values()),
            "created_total": sum(data["row_totals"].values()),
        }
        for view, data in result["views"].items()
    }, indent=2))


if __name__ == "__main__":
    main()
