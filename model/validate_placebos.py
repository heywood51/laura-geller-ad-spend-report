"""Compare observed halo with time-shifted placebos and produce conservative estimates."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from halo_model import build_halo


Z80 = 1.2815515655446004


def benjamini_hochberg(p_values: dict[str, float]) -> dict[str, float]:
    """Control the false-discovery rate across the entire halo matrix."""
    ordered = sorted(p_values, key=p_values.get)
    total = len(ordered)
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank in range(total, 0, -1):
        key = ordered[rank - 1]
        running = min(running, p_values[key] * total / rank)
        adjusted[key] = float(min(running, 1.0))
    return adjusted


def adjust_model(
    observed_model: dict,
    placebo_effects: dict[str, dict[str, list[float]]],
    alpha: float,
) -> dict:
    """Debias each cell, subtract its empirical-null threshold, and FDR-gate it."""
    result = json.loads(json.dumps(observed_model))
    for view_name, view in result["views"].items():
        p_values: dict[str, float] = {}
        summaries: dict[str, dict[str, float]] = {}
        for key, cell in view["cells"].items():
            values = np.asarray(placebo_effects[view_name][key], dtype=float)
            bias = float(np.median(values))
            centered = values - bias
            debiased = float(cell["effect"] - bias)
            threshold = float(np.quantile(np.abs(centered), 1.0 - alpha, method="higher"))
            null_sd = float(1.4826 * np.median(np.abs(centered)))
            null_sd = max(null_sd, 1e-9)
            empirical_p = float((1 + np.sum(np.abs(centered) >= abs(debiased))) / (len(values) + 1))
            # The empirical p-value is resolution-limited to 1/(runs+1), which is too
            # coarse for 168 simultaneous tests. Use the robust empirical-null scale
            # for a continuous two-sided tail probability, while retaining the direct
            # empirical value for auditability and using the empirical 95% threshold.
            p_value = float(math.erfc(abs(debiased) / null_sd / math.sqrt(2.0)))
            summaries[key] = {
                "bias": bias,
                "debiased": debiased,
                "threshold": threshold,
                "p_value": p_value,
                "empirical_p": empirical_p,
                "null_sd": null_sd,
            }
            p_values[key] = p_value
        q_values = benjamini_hochberg(p_values)
        row_totals = {channel: 0.0 for channel in result["channels"]}
        for key, cell in view["cells"].items():
            summary = summaries[key]
            passes = q_values[key] <= alpha and abs(summary["debiased"]) > summary["threshold"]
            adjusted = (
                float(np.sign(summary["debiased"]) * (abs(summary["debiased"]) - summary["threshold"]))
                if passes else 0.0
            )
            combined_se = float(np.hypot(cell["standard_error"], summary["null_sd"]))
            cell.update({
                "raw_effect": cell["effect"],
                "effect": adjusted,
                "lower80": adjusted - Z80 * combined_se,
                "upper80": adjusted + Z80 * combined_se,
                "standard_error": combined_se,
                "probability_positive": 0.5 if adjusted == 0 else float(
                    0.5 * (1.0 + math.erf(adjusted / max(combined_se, 1e-9) / np.sqrt(2.0)))
                ),
                "placebo_adjusted": True,
                "publishable": True,
                "passes_placebo": bool(passes),
                "placebo_bias": summary["bias"],
                "placebo_threshold": summary["threshold"],
                "placebo_p_value": summary["p_value"],
                "placebo_empirical_p_value": summary["empirical_p"],
                "placebo_q_value": q_values[key],
                "placebo_runs": len(placebo_effects[view_name][key]),
            })
            row_totals[key.split("|", 1)[0]] += adjusted
        view["row_totals"] = row_totals
    result["status"] = "placebo_adjusted_observational"
    result["warning"] = (
        "Cell-specific time-shift placebos were used to remove empirical bias, subtract a 95% false-signal threshold, "
        "and control false discoveries. These are conservative observational estimates, not randomized causal proof."
    )
    result["metadata"]["placebo_runs"] = len(next(iter(next(iter(placebo_effects.values())).values())))
    result["metadata"]["placebo_alpha"] = alpha
    result["metadata"]["method"] += " with empirical-null debiasing and FDR control"
    return result


def matrix_scores(model: dict) -> dict[str, float]:
    view = model["views"]["Total"]
    effects = np.array([cell["effect"] for cell in view["cells"].values()], dtype=float)
    row_totals = np.array(list(view["row_totals"].values()), dtype=float)
    return {
        "absolute_cell_volume": float(np.abs(effects).sum()),
        "net_cell_volume": float(effects.sum()),
        "absolute_row_volume": float(np.abs(row_totals).sum()),
        "net_row_volume": float(row_totals.sum()),
    }


def shifted_panel(frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, dict[str, int]]:
    result = frame.copy()
    date_column = config["date_column"]
    geo_column = config["geo_column"]
    dates = np.array(sorted(result[date_column].unique()))
    offsets: dict[str, int] = {}
    for channel, settings in config["channels"].items():
        offset = int(rng.integers(45, max(46, len(dates) - 45)))
        offsets[channel] = offset
        for geo in result[geo_column].unique():
            mask = result[geo_column].eq(geo)
            ordered = result.loc[mask].sort_values(date_column)
            values = ordered[settings["column"]].to_numpy(float)
            result.loc[ordered.index, settings["column"]] = np.roll(values, offset)
    return result, offsets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--adjusted-output")
    parser.add_argument("--runs", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260820)
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    with open(args.config, encoding="utf8") as handle:
        config = json.load(handle)
    rng = np.random.default_rng(args.seed)
    observed_model = build_halo(frame, config)
    observed = matrix_scores(observed_model)
    placebo_effects = {
        view_name: {key: [] for key in view["cells"]}
        for view_name, view in observed_model["views"].items()
    }
    placebos = []
    for run in range(args.runs):
        shifted, offsets = shifted_panel(frame, config, rng)
        placebo_model = build_halo(shifted, config)
        scores = matrix_scores(placebo_model)
        for view_name, view in placebo_model["views"].items():
            for key, cell in view["cells"].items():
                placebo_effects[view_name][key].append(float(cell["effect"]))
        scores["run"] = run + 1
        scores["offsets"] = offsets
        placebos.append(scores)

    absolute = np.array([item["absolute_cell_volume"] for item in placebos])
    net = np.array([abs(item["net_cell_volume"]) for item in placebos])
    result = {
        "observed": observed,
        "placebos": placebos,
        "summary": {
            "placebo_absolute_cell_median": float(np.median(absolute)),
            "placebo_absolute_cell_max": float(np.max(absolute)),
            "observed_to_placebo_absolute_median": float(observed["absolute_cell_volume"] / np.median(absolute)),
            "placebo_abs_net_median": float(np.median(net)),
            "observed_to_placebo_abs_net_median": float(abs(observed["net_cell_volume"]) / max(np.median(net), 1e-9)),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf8")
    if args.adjusted_output:
        adjusted = adjust_model(observed_model, placebo_effects, args.alpha)
        adjusted_path = Path(args.adjusted_output)
        adjusted_path.parent.mkdir(parents=True, exist_ok=True)
        adjusted_path.write_text(json.dumps(adjusted, indent=2, allow_nan=False), encoding="utf8")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
