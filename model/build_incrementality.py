"""Fit source-to-total-business effects and apply empirical-null correction."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from halo_model import build_halo
from validate_placebos import adjust_model, matrix_scores, shifted_panel


def build_total_config(frame: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    """Replace attributed destinations with their total-business outcome."""
    result = frame.copy()
    destination_columns = list(config["destinations"].values())
    result["_total_business"] = result[destination_columns].sum(axis=1)
    total_config = copy.deepcopy(config)
    total_config["destinations"] = {"Total Business": "_total_business"}
    total_config["model_purpose"] = "source-level total-business incrementality"
    return result, total_config


def run_model(
    frame: pd.DataFrame,
    config: dict,
    runs: int,
    seed: int,
    alpha: float,
) -> tuple[dict, dict]:
    frame, config = build_total_config(frame, config)
    rng = np.random.default_rng(seed)
    observed_model = build_halo(frame, config)
    observed = matrix_scores(observed_model)
    placebo_effects = {
        view_name: {key: [] for key in view["cells"]}
        for view_name, view in observed_model["views"].items()
    }
    placebos = []
    for run in range(runs):
        shifted, offsets = shifted_panel(frame, config, rng)
        placebo_model = build_halo(shifted, config)
        scores = matrix_scores(placebo_model)
        for view_name, view in placebo_model["views"].items():
            for key, cell in view["cells"].items():
                placebo_effects[view_name][key].append(float(cell["effect"]))
        scores["run"] = run + 1
        scores["offsets"] = offsets
        placebos.append(scores)
        if (run + 1) % 10 == 0:
            print(f"completed {run + 1}/{runs} placebo refits", flush=True)

    adjusted = adjust_model(observed_model, placebo_effects, alpha)
    adjusted["metadata"]["model_purpose"] = config["model_purpose"]
    absolute = np.asarray([item["absolute_cell_volume"] for item in placebos])
    net = np.asarray([abs(item["net_cell_volume"]) for item in placebos])
    fake_share = float(np.median(absolute) / max(observed["absolute_cell_volume"], 1e-9))
    split = max(1, runs // 2)
    calibration = {
        view_name: {key: values[:split] for key, values in cells.items()}
        for view_name, cells in placebo_effects.items()
    }
    def decision_score(model: dict) -> dict:
        cells = model["views"]["Total"]["cells"].values()
        accepted = [
            cell for cell in cells
            if cell["passes_placebo"] and cell["effect"] > 0 and cell["lower80"] > 0
        ]
        return {
            "absolute_volume": float(sum(abs(cell["effect"]) for cell in accepted)),
            "passing_rows": len(accepted),
        }

    heldout_adjusted_scores = []
    for index in range(split, runs):
        candidate = copy.deepcopy(observed_model)
        for view_name, view in candidate["views"].items():
            for key, cell in view["cells"].items():
                cell["effect"] = placebo_effects[view_name][key][index]
        heldout_adjusted = adjust_model(candidate, calibration, alpha)
        score = decision_score(heldout_adjusted)
        heldout_adjusted_scores.append(score)
    adjusted_observed_score = decision_score(adjusted)
    heldout_absolute = np.asarray([
        item["absolute_volume"] for item in heldout_adjusted_scores
    ])
    heldout_passing = np.asarray([item["passing_rows"] for item in heldout_adjusted_scores])
    validation = {
        "model_purpose": config["model_purpose"],
        "observed": observed,
        "placebos": placebos,
        "summary": {
            "placebo_absolute_cell_median": float(np.median(absolute)),
            "placebo_absolute_cell_max": float(np.max(absolute)),
            "observed_absolute_cell_volume": float(observed["absolute_cell_volume"]),
            "fake_to_observed_absolute_median": fake_share,
            "observed_to_placebo_absolute_median": float(1.0 / max(fake_share, 1e-9)),
            "placebo_abs_net_median": float(np.median(net)),
            "passing_total_business_rows": int(sum(
                cell["passes_placebo"]
                for cell in adjusted["views"]["Total"]["cells"].values()
            )),
            "tested_total_business_rows": len(adjusted["channels"]),
            "adjusted_observed_absolute_volume": float(adjusted_observed_score["absolute_volume"]),
            "heldout_adjusted_fake_absolute_median": float(np.median(heldout_absolute)),
            "heldout_adjusted_fake_absolute_max": float(np.max(heldout_absolute)),
            "heldout_fake_to_adjusted_observed_median": float(
                np.median(heldout_absolute)
                / max(adjusted_observed_score["absolute_volume"], 1e-9)
            ),
            "heldout_fake_passing_rows_median": float(np.median(heldout_passing)),
            "heldout_fake_passing_rows_max": int(np.max(heldout_passing)),
            "heldout_placebo_runs": int(len(heldout_adjusted_scores)),
        },
        "heldout_adjusted_placebos": heldout_adjusted_scores,
        "placebo_effects": placebo_effects,
    }
    return adjusted, validation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--validation-output", required=True)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20260824)
    parser.add_argument("--alpha", type=float, default=0.01)
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    with open(args.config, encoding="utf8") as handle:
        config = json.load(handle)
    adjusted, validation = run_model(frame, config, args.runs, args.seed, args.alpha)
    Path(args.output).write_text(json.dumps(adjusted, indent=2, allow_nan=False), encoding="utf8")
    Path(args.validation_output).write_text(json.dumps(validation, indent=2, allow_nan=False), encoding="utf8")
    print(json.dumps(validation["summary"], indent=2))


if __name__ == "__main__":
    main()
