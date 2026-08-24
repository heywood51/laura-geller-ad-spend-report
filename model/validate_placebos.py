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


def parse_lead_days(value: str) -> tuple[int, ...]:
    """Parse a comma-separated list of strictly positive daily leads."""
    leads = tuple(sorted({int(item.strip()) for item in value.split(",") if item.strip()}))
    if not leads or any(lead <= 0 for lead in leads):
        raise argparse.ArgumentTypeError("lead days must be positive comma-separated integers")
    return leads


def trim_panel_for_leads(frame: pd.DataFrame, config: dict, max_lead: int) -> pd.DataFrame:
    """Use one common sample that has future exposure available for every lead."""
    date_column = config["date_column"]
    geo_column = config["geo_column"]
    ordered = frame.copy()
    ordered[date_column] = pd.to_datetime(ordered[date_column], errors="raise")
    ordered = ordered.sort_values([geo_column, date_column])
    position = ordered.groupby(geo_column).cumcount()
    size = ordered.groupby(geo_column)[geo_column].transform("size")
    return ordered.loc[position < size - max_lead].copy().reset_index(drop=True)


def future_exposure_panel(
    frame: pd.DataFrame,
    config: dict,
    channel: str,
    lead: int,
    max_lead: int,
) -> pd.DataFrame:
    """Put exposure from t+lead on row t without circular wraparound."""
    date_column = config["date_column"]
    geo_column = config["geo_column"]
    exposure_column = config["channels"][channel]["column"]
    ordered = frame.copy()
    ordered[date_column] = pd.to_datetime(ordered[date_column], errors="raise")
    ordered = ordered.sort_values([geo_column, date_column])
    future = ordered.groupby(geo_column)[exposure_column].shift(-lead)
    position = ordered.groupby(geo_column).cumcount()
    size = ordered.groupby(geo_column)[geo_column].transform("size")
    eligible = position < size - max_lead
    result = ordered.loc[eligible].copy()
    result[exposure_column] = future.loc[eligible].to_numpy()
    return result.reset_index(drop=True)


def build_lead_falsification(
    frame: pd.DataFrame,
    config: dict,
    lead_days: tuple[int, ...],
) -> tuple[dict, dict[int, dict]]:
    """Fit current-timing and future-exposure models on an identical sample."""
    max_lead = max(lead_days)
    reference = build_halo(trim_panel_for_leads(frame, config, max_lead), config)
    lead_models: dict[int, dict] = {}
    for channel in config["channels"]:
        for lead in lead_days:
            shifted = future_exposure_panel(frame, config, channel, lead, max_lead)
            model = build_halo(shifted, config)
            lead_models.setdefault(lead, {})[channel] = model
    return reference, lead_models


def apply_lead_falsification(
    adjusted_model: dict,
    reference_model: dict,
    lead_models: dict[int, dict],
    lead_days: tuple[int, ...],
) -> dict:
    """Reject a cell when future exposure explains as much as correct-timing exposure."""
    result = json.loads(json.dumps(adjusted_model))
    passed = 0
    tested = 0
    for view_name, view in result["views"].items():
        for key, cell in view["cells"].items():
            source = key.split("|", 1)[0]
            current_raw = float(reference_model["views"][view_name]["cells"][key]["effect"])
            null_bias = float(cell.get("placebo_bias", 0.0))
            current = current_raw - null_bias
            lead_effects = {
                str(lead): float(
                    lead_models[lead][source]["views"][view_name]["cells"][key]["effect"]
                    - null_bias
                )
                for lead in lead_days
            }
            max_abs_lead = max(abs(value) for value in lead_effects.values())
            lead_passes = abs(current) > max_abs_lead
            empirical_passes = bool(cell.get("passes_empirical_null", cell["passes_placebo"]))
            passes_validation = empirical_passes and lead_passes
            cell.update({
                "passes_empirical_null": empirical_passes,
                "passes_lead_falsification": bool(lead_passes),
                "passes_validation": bool(passes_validation),
                "lead_reference_effect": current,
                "lead_effects": lead_effects,
                "max_abs_lead_effect": float(max_abs_lead),
                "lead_to_reference_ratio": float(max_abs_lead / max(abs(current), 1e-9)),
                # Backward-compatible publication gate used by downstream builders.
                "passes_placebo": bool(passes_validation),
            })
            tested += 1
            passed += int(lead_passes)
            if not passes_validation:
                cell["effect"] = 0.0
                cell["lower80"] = -Z80 * float(cell["standard_error"])
                cell["upper80"] = Z80 * float(cell["standard_error"])
                cell["probability_positive"] = 0.5
        view["row_totals"] = {
            channel: float(sum(
                item["effect"]
                for item_key, item in view["cells"].items()
                if item_key.split("|", 1)[0] == channel
            ))
            for channel in result["channels"]
        }
    result["metadata"]["lead_falsification_days"] = list(lead_days)
    result["metadata"]["lead_falsification_passed_cells"] = passed
    result["metadata"]["lead_falsification_tested_cells"] = tested
    result["metadata"]["method"] += " with directed future-exposure lead falsification"
    result["status"] = "placebo_and_lead_adjusted_observational"
    result["warning"] = (
        "Effects must survive empirical-null correction and a directed reverse-causality test. "
        "A cell is withheld when future exposure predicts the outcome at least as strongly as correctly timed exposure. "
        "Passing estimates remain observational, not randomized causal proof."
    )
    return result


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
    parser.add_argument("--lead-days", type=parse_lead_days, default=(1, 2, 3, 7, 14))
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
        reference, lead_models = build_lead_falsification(frame, config, args.lead_days)
        adjusted = apply_lead_falsification(
            adjusted, reference, lead_models, args.lead_days
        )
        adjusted_path = Path(args.adjusted_output)
        adjusted_path.parent.mkdir(parents=True, exist_ok=True)
        adjusted_path.write_text(json.dumps(adjusted, indent=2, allow_nan=False), encoding="utf8")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
