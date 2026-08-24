"""Build a diagonal-anchored, column-balanced halo allocation.

The strict total-business model supplies source evidence. The destination model
supplies routing evidence. Off-diagonal halo is uncertainty-discounted, capped
at the destination's scenario attribution benchmark, and the remaining credit
stays on the destination diagonal (or in an explicit unassigned bucket when a
destination has no matching source row).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


INTERVAL_MULTIPLIER = 1.2815515655
NON_ADDRESSABLE_SOURCES = {"Television"}


def evidence_weight(cell: dict) -> float:
    """Combine interval precision and timing separation continuously."""
    effect = max(0.0, float(cell["effect"]))
    if not cell["passes_placebo"] or effect == 0:
        return 0.0
    margin = INTERVAL_MULTIPLIER * max(0.0, float(cell["standard_error"]))
    interval_weight = effect / (effect + margin) if effect + margin else 0.0
    if not cell.get("passes_lead_falsification", True):
        return 0.0
    timing_ratio = max(0.0, float(cell.get("lead_to_reference_ratio", 0.0)))
    timing_weight = max(0.0, min(1.0, 1.0 - timing_ratio))
    return interval_weight * timing_weight


def timing_weight(cell: dict) -> float:
    if not cell.get("passes_lead_falsification", True):
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(cell.get("lead_to_reference_ratio", 0.0))))


def build_balanced_matrix(
    total_model: dict,
    routing_model: dict,
    summary: dict,
    non_addressable_sources: set[str] | None = None,
) -> dict:
    non_addressable_sources = non_addressable_sources or NON_ADDRESSABLE_SOURCES
    measure = total_model["metadata"]["measure"]
    scenario_share = abs(float(summary["scenario_relative_change"]))
    result = {
        "status": "diagonal_anchored_observational_allocation",
        "warning": "Off-diagonal values are uncertainty- and timing-weighted observational scenarios, not causal facts. Plausible ranges retain the valid model uncertainty; diagonal values retain original attribution needed for exact column reconciliation.",
        "metadata": {
            **routing_model["metadata"],
            "method": "continuous interval and timing reliability, corrected positive routing, plausible ranges, diagonal residual balancing",
            "measure": measure,
            "scenario_share": scenario_share,
            "non_addressable_sources": sorted(non_addressable_sources),
        },
        "channels": list(routing_model["channels"]),
        "destinations": list(routing_model["destinations"]),
        "views": {},
    }

    for view_name, route_view in routing_model["views"].items():
        total_view = total_model["views"][view_name]
        benchmark = {
            d: float(summary["views"][view_name][measure][d]) * scenario_share
            for d in result["destinations"]
        }
        candidates: dict[tuple[str, str], float] = {}
        candidate_low: dict[tuple[str, str], float] = {}
        candidate_high: dict[tuple[str, str], float] = {}
        source_evidence = {}
        for source in result["channels"]:
            total_cell = total_view["cells"][f"{source}|Total Business"]
            reliability = evidence_weight(total_cell)
            evidence_budget = max(0.0, float(total_cell["effect"])) * reliability
            low_budget = max(0.0, float(total_cell["lower80"])) * timing_weight(total_cell)
            high_budget = (
                max(0.0, float(total_cell["upper80"]))
                if total_cell["passes_placebo"] else 0.0
            )
            routes = []
            for destination in result["destinations"]:
                if destination == source:
                    continue
                route = route_view["cells"][f"{source}|{destination}"]
                raw_value = max(0.0, float(route["effect"])) if route["passes_placebo"] else 0.0
                weighted_value = raw_value * evidence_weight(route) if raw_value else 0.0
                if raw_value:
                    routes.append((destination, raw_value, weighted_value))
            route_sum = sum(weighted for _, _, weighted in routes)
            raw_route_sum = sum(raw for _, raw, _ in routes)
            for destination, raw_value, weighted_value in routes:
                point_share = weighted_value / route_sum if route_sum else 0.0
                range_share = raw_value / raw_route_sum if raw_route_sum else 0.0
                candidates[source, destination] = evidence_budget * point_share
                candidate_low[source, destination] = low_budget * point_share
                candidate_high[source, destination] = high_budget * range_share
            source_evidence[source] = {
                "adjusted_total_effect": float(total_cell["effect"]),
                "lower80": float(total_cell["lower80"]),
                "upper80": float(total_cell["upper80"]),
                "passes_placebo": bool(total_cell["passes_placebo"]),
                "passes_empirical_null": bool(total_cell.get("passes_empirical_null", total_cell["passes_placebo"])),
                "passes_lead_falsification": bool(total_cell.get("passes_lead_falsification", False)),
                "lead_effects": total_cell.get("lead_effects", {}),
                "lead_to_reference_ratio": float(total_cell.get("lead_to_reference_ratio", 0.0)),
                "reliability_weight": reliability,
                "interval_reliability_weight": (
                    reliability / timing_weight(total_cell) if timing_weight(total_cell) else 0.0
                ),
                "timing_reliability_weight": timing_weight(total_cell),
                "halo_budget": evidence_budget,
                "halo_budget_low": low_budget,
                "halo_budget_high": high_budget,
            }

        # A destination can never receive more reallocated halo than its
        # original-attribution benchmark on the same scenario basis.
        for destination in result["destinations"]:
            incoming = sum(candidates.get((s, destination), 0.0) for s in result["channels"])
            scale = min(1.0, benchmark[destination] / incoming) if incoming else 1.0
            incoming_low = sum(candidate_low.get((s, destination), 0.0) for s in result["channels"])
            low_scale = min(1.0, benchmark[destination] / incoming_low) if incoming_low else 1.0
            incoming_high = sum(candidate_high.get((s, destination), 0.0) for s in result["channels"])
            high_scale = min(1.0, benchmark[destination] / incoming_high) if incoming_high else 1.0
            for source in result["channels"]:
                candidates[source, destination] = candidates.get((source, destination), 0.0) * scale
                candidate_low[source, destination] = candidate_low.get((source, destination), 0.0) * low_scale
                candidate_high[source, destination] = candidate_high.get((source, destination), 0.0) * high_scale
                candidate_low[source, destination] = min(
                    candidate_low[source, destination], candidates[source, destination]
                )
                candidate_high[source, destination] = max(
                    candidate_high[source, destination], candidates[source, destination]
                )

        cells = {}
        column_reconciliation = {}
        for destination in result["destinations"]:
            halo = sum(candidates[source, destination] for source in result["channels"])
            halo_low = sum(candidate_low[source, destination] for source in result["channels"])
            halo_high = sum(candidate_high[source, destination] for source in result["channels"])
            retained = max(0.0, benchmark[destination] - halo)
            has_diagonal = (
                destination in result["channels"]
                and destination not in non_addressable_sources
            )
            column_reconciliation[destination] = {
                "benchmark": benchmark[destination],
                "cross_source_halo": halo,
                "cross_source_halo_low": halo_low,
                "cross_source_halo_high": halo_high,
                "retained_self_attribution": retained if has_diagonal else 0.0,
                "unassigned_original_attribution": retained if not has_diagonal else 0.0,
            }
            for source in result["channels"]:
                route = route_view["cells"][f"{source}|{destination}"]
                source_total_cell = total_view["cells"][f"{source}|Total Business"]
                is_diagonal = source == destination
                structural_zero = is_diagonal and source in non_addressable_sources
                effect = retained if is_diagonal and has_diagonal else candidates[source, destination]
                if is_diagonal and has_diagonal:
                    range_low = max(0.0, benchmark[destination] - halo_high)
                    range_high = max(0.0, benchmark[destination] - halo_low)
                    evidence_status = "accounting_anchor"
                elif structural_zero:
                    range_low = range_high = 0.0
                    evidence_status = "structural_zero"
                else:
                    range_low = candidate_low[source, destination]
                    range_high = candidate_high[source, destination]
                    total_supported = float(source_total_cell["lower80"]) > 0
                    route_supported = float(route.get("lower80", 0.0)) > 0
                    evidence_status = (
                        "supported" if effect > 0 and total_supported and route_supported
                        else "possible" if effect > 0
                        else "unresolved"
                    )
                cells[f"{source}|{destination}"] = {
                    "effect": effect,
                    "range_low": range_low,
                    "range_high": range_high,
                    "evidence_status": evidence_status,
                    "kind": (
                        "structural_zero_non_addressable"
                        if structural_zero
                        else "retained_self_attribution"
                        if is_diagonal
                        else "cross_source_halo"
                    ),
                    "publishable": bool(effect > 0),
                    "passes_placebo": bool(effect > 0),
                    "routing_effect": float(route["effect"]),
                    "routing_passes": bool(route["passes_placebo"]),
                    "routing_passes_empirical_null": bool(route.get("passes_empirical_null", route["passes_placebo"])),
                    "routing_passes_lead_falsification": bool(route.get("passes_lead_falsification", False)),
                    "routing_lead_effects": route.get("lead_effects", {}),
                    "routing_lead_to_reference_ratio": float(route.get("lead_to_reference_ratio", 0.0)),
                    "source_evidence": source_evidence[source],
                }
        row_totals = {
            source: sum(cells[f"{source}|{d}"]["effect"] for d in result["destinations"])
            for source in result["channels"]
        }
        result["views"][view_name] = {
            "cells": cells,
            "row_totals": row_totals,
            "column_reconciliation": column_reconciliation,
            "unassigned_total": sum(x["unassigned_original_attribution"] for x in column_reconciliation.values()),
            "source_evidence": source_evidence,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--incrementality", required=True)
    parser.add_argument("--routing", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with open(args.incrementality, encoding="utf8") as handle:
        total = json.load(handle)
    with open(args.routing, encoding="utf8") as handle:
        routing = json.load(handle)
    with open(args.summary, encoding="utf8") as handle:
        summary = json.load(handle)
    result = build_balanced_matrix(total, routing, summary)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf8")
    print(json.dumps({view: data["row_totals"] for view, data in result["views"].items()}, indent=2))


if __name__ == "__main__":
    main()
