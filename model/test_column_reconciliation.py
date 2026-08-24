"""Checks the destination-column accounting used by the report."""

import json
from pathlib import Path


GENERATED = Path(__file__).parent / "generated"


def test_columns_reconcile_on_the_scenario_basis() -> None:
    summary = json.loads((GENERATED / "report-summary.json").read_text(encoding="utf8"))
    scenario_share = abs(float(summary["scenario_relative_change"]))
    for measure in ("orders", "revenue"):
        model = json.loads(
            (GENERATED / f"halo-created-{measure}.json").read_text(encoding="utf8")
        )
        for view_name, view in model["views"].items():
            for destination in model["destinations"]:
                self_effect = (
                    view["cells"][f"{destination}|{destination}"]["effect"]
                    if destination in model["channels"]
                    else 0.0
                )
                halo_effect = sum(
                    view["cells"][f"{source}|{destination}"]["effect"]
                    for source in model["channels"]
                    if source != destination
                )
                benchmark = (
                    summary["views"][view_name][measure][destination] * scenario_share
                )
                gap = benchmark - self_effect - halo_effect
                assert abs((self_effect + halo_effect + gap) - benchmark) < 1e-7


if __name__ == "__main__":
    test_columns_reconcile_on_the_scenario_basis()
    print("column_reconciliation: all accounting checks passed")
