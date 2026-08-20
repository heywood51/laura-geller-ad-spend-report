"""Experiment-calibrated, geo-level Bayesian halo matrix.

The model is deliberately dependency-light: NumPy and pandas are sufficient. It
uses conjugate Gaussian updating for a regularized multivariate distributed-lag
model. Experiment results enter as noisy linear observations of the exact same
counterfactual used to populate the matrix.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EPSILON = 1e-9


def geometric_adstock(values: np.ndarray, half_life: float) -> np.ndarray:
    decay = 0.5 ** (1.0 / max(float(half_life), 0.05))
    output = np.zeros_like(values, dtype=float)
    state = 0.0
    for index, value in enumerate(np.nan_to_num(values, nan=0.0)):
        state = max(float(value), 0.0) + decay * state
        output[index] = state
    return output


def hill(values: np.ndarray, midpoint: float, slope: float) -> np.ndarray:
    clean = np.maximum(np.nan_to_num(values, nan=0.0), 0.0)
    midpoint = max(float(midpoint), EPSILON)
    slope = max(float(slope), 0.1)
    numerator = np.power(clean, slope)
    return numerator / (numerator + midpoint**slope + EPSILON)


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


@dataclass
class Design:
    raw: np.ndarray
    scaled: np.ndarray
    names: list[str]
    means: np.ndarray
    scales: np.ndarray
    media_midpoints: dict[str, float]


def validate_columns(frame: pd.DataFrame, config: dict[str, Any]) -> None:
    required = {config["date_column"], config["geo_column"], *config.get("controls", [])}
    required.update(item["column"] for item in config["channels"].values())
    required.update(config["destinations"].values())
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Input is missing required columns: {', '.join(missing)}")


def prepare_frame(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    result = frame.copy()
    result[config["date_column"]] = pd.to_datetime(result[config["date_column"]], errors="raise")
    if config.get("include_geos"):
        result = result[result[config["geo_column"]].isin(config["include_geos"])].copy()
    result = result.sort_values([config["geo_column"], config["date_column"]]).reset_index(drop=True)
    numeric_columns = [*config.get("controls", [])]
    numeric_columns += [item["column"] for item in config["channels"].values()]
    numeric_columns += list(config["destinations"].values())
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    if result.empty:
        raise ValueError("No rows remain after applying the configured geography filter")
    return result


def transformed_media(
    frame: pd.DataFrame,
    config: dict[str, Any],
    multipliers: dict[str, np.ndarray] | None = None,
    fixed_midpoints: dict[str, float] | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    geo_column = config["geo_column"]
    transformed: dict[str, np.ndarray] = {}
    midpoints: dict[str, float] = {}
    for channel, settings in config["channels"].items():
        exposure = frame[settings["column"]].to_numpy(float)
        if multipliers and channel in multipliers:
            exposure = exposure * multipliers[channel]
        stocked = np.zeros(len(frame), dtype=float)
        for geo in frame[geo_column].drop_duplicates():
            mask = frame[geo_column].eq(geo).to_numpy()
            stocked[mask] = geometric_adstock(exposure[mask], settings.get("half_life_periods", 1.0))
        positive = stocked[stocked > 0]
        inferred = float(np.median(positive)) if len(positive) else 1.0
        midpoint = float((fixed_midpoints or {}).get(channel, settings.get("half_saturation", inferred)))
        midpoints[channel] = midpoint
        transformed[channel] = hill(stocked, midpoint, settings.get("slope", 1.0))
    return transformed, midpoints


def raw_design(
    frame: pd.DataFrame,
    config: dict[str, Any],
    media: dict[str, np.ndarray],
) -> tuple[np.ndarray, list[str]]:
    geo_column = config["geo_column"]
    date_column = config["date_column"]
    geos = list(frame[geo_column].drop_duplicates())
    columns: list[np.ndarray] = []
    names: list[str] = []

    for geo in geos:
        mask = frame[geo_column].eq(geo).to_numpy(float)
        columns.append(mask)
        names.append(f"baseline:intercept:{geo}")
        order = np.zeros(len(frame), dtype=float)
        count = int(mask.sum())
        if count > 1:
            order[mask.astype(bool)] = np.linspace(-1.0, 1.0, count)
        columns.append(order)
        names.append(f"baseline:trend:{geo}")

    start = frame[date_column].min()
    elapsed_days = (frame[date_column] - start).dt.days.to_numpy(float)
    period_days = 365.25
    for harmonic in (1, 2):
        angle = 2.0 * np.pi * harmonic * elapsed_days / period_days
        columns.extend([np.sin(angle), np.cos(angle)])
        names.extend([f"baseline:season_sin_{harmonic}", f"baseline:season_cos_{harmonic}"])

    for control in config.get("controls", []):
        columns.append(frame[control].to_numpy(float))
        names.append(f"control:{control}")

    reference_geo = geos[0]
    for channel, values in media.items():
        columns.append(values)
        names.append(f"media:{channel}")
        for geo in geos[1:]:
            columns.append(values * frame[geo_column].eq(geo).to_numpy(float))
            names.append(f"media_geo:{channel}:{geo}:vs:{reference_geo}")

    return np.column_stack(columns), names


def build_design(frame: pd.DataFrame, config: dict[str, Any]) -> Design:
    media, midpoints = transformed_media(frame, config)
    raw, names = raw_design(frame, config, media)
    means = raw.mean(axis=0)
    scales = raw.std(axis=0)
    indicator = np.array([name.startswith("baseline:intercept") for name in names])
    means[indicator] = 0.0
    scales[indicator] = 1.0
    scales[scales < EPSILON] = 1.0
    return Design(raw=raw, scaled=(raw - means) / scales, names=names, means=means, scales=scales, media_midpoints=midpoints)


def prior_variances(names: list[str], config: dict[str, Any]) -> np.ndarray:
    settings = config.get("priors", {})
    output = []
    for name in names:
        if name.startswith("media_geo:"):
            sd = settings.get("media_geo_deviation_sd", 0.35)
        elif name.startswith("media:"):
            sd = settings.get("media_sd", 1.0)
        elif name.startswith("control:"):
            sd = settings.get("control_sd", 2.0)
        else:
            sd = settings.get("baseline_sd", 10.0)
        output.append(float(sd) ** 2)
    return np.asarray(output)


def counterfactual_delta(
    frame: pd.DataFrame,
    config: dict[str, Any],
    design: Design,
    channel: str,
    relative_change: float,
    row_mask: np.ndarray,
) -> np.ndarray:
    multiplier = np.ones(len(frame), dtype=float)
    multiplier[row_mask] = 1.0 + float(relative_change)
    media, _ = transformed_media(
        frame,
        config,
        multipliers={channel: multiplier},
        fixed_midpoints=design.media_midpoints,
    )
    raw_counterfactual, names = raw_design(frame, config, media)
    if names != design.names:
        raise RuntimeError("Counterfactual design columns changed unexpectedly")
    scaled_counterfactual = (raw_counterfactual - design.means) / design.scales
    return design.scaled - scaled_counterfactual


def experiment_updates(
    frame: pd.DataFrame,
    config: dict[str, Any],
    design: Design,
    destination: str,
    y_scale: float,
) -> list[tuple[np.ndarray, float, float]]:
    date_column = config["date_column"]
    geo_column = config["geo_column"]
    updates = []
    for experiment in config.get("experiments", []):
        if experiment["destination"] != destination:
            continue
        mask = np.ones(len(frame), dtype=bool)
        if experiment.get("geo"):
            mask &= frame[geo_column].eq(experiment["geo"]).to_numpy()
        if experiment.get("start"):
            mask &= frame[date_column].ge(pd.Timestamp(experiment["start"])).to_numpy()
        if experiment.get("end"):
            mask &= frame[date_column].le(pd.Timestamp(experiment["end"])).to_numpy()
        delta = counterfactual_delta(
            frame,
            config,
            design,
            experiment["channel"],
            experiment["relative_change"],
            mask,
        ).sum(axis=0)
        updates.append((
            delta,
            -float(experiment["effect"]) / y_scale,
            max(float(experiment["standard_error"]) / y_scale, 1e-4),
        ))
    return updates


def fit_destination(
    frame: pd.DataFrame,
    config: dict[str, Any],
    design: Design,
    destination: str,
) -> dict[str, Any]:
    y = frame[config["destinations"][destination]].to_numpy(float)
    y_mean = float(y.mean())
    y_scale = max(float(y.std()), 1.0)
    ys = (y - y_mean) / y_scale
    x = design.scaled
    variances = prior_variances(design.names, config)
    prior_precision = np.diag(1.0 / np.maximum(variances, EPSILON))

    initial = np.linalg.solve(x.T @ x + prior_precision, x.T @ ys)
    residual = ys - x @ initial
    dof = max(len(ys) - min(x.shape[1], len(ys) // 3), 10)
    sigma2 = max(float(residual @ residual / dof), 0.05**2)
    precision = x.T @ x / sigma2 + prior_precision
    right = x.T @ ys / sigma2

    experiment_count = 0
    for delta, observed, standard_error in experiment_updates(
        frame, config, design, destination, y_scale
    ):
        precision += np.outer(delta, delta) / (standard_error**2)
        right += delta * observed / (standard_error**2)
        experiment_count += 1

    covariance = np.linalg.pinv(precision)
    coefficients = covariance @ right
    fitted = y_mean + y_scale * (x @ coefficients)
    denominator = float(np.sum((y - y_mean) ** 2))
    r_squared = 1.0 - float(np.sum((y - fitted) ** 2)) / max(denominator, EPSILON)
    return {
        "coefficients": coefficients,
        "covariance": covariance,
        "y_scale": y_scale,
        "r_squared": r_squared,
        "experiment_count": experiment_count,
    }


def scenario_mask(frame: pd.DataFrame, config: dict[str, Any], geo: str | None) -> np.ndarray:
    date_column = config["date_column"]
    geo_column = config["geo_column"]
    mask = np.ones(len(frame), dtype=bool)
    if geo:
        mask &= frame[geo_column].eq(geo).to_numpy()
    dates = frame.loc[mask, date_column]
    periods = int(config["scenario"].get("periods", config.get("periods_per_year", 52)))
    if len(dates):
        unique_dates = sorted(dates.unique())
        cutoff = unique_dates[max(0, len(unique_dates) - periods)]
        mask &= frame[date_column].ge(cutoff).to_numpy()
    return mask


def summarize_cell(delta: np.ndarray, fit: dict[str, Any]) -> dict[str, Any]:
    mean = float(delta @ fit["coefficients"]) * fit["y_scale"]
    variance = float(delta @ fit["covariance"] @ delta) * fit["y_scale"] ** 2
    standard_error = math.sqrt(max(variance, 0.0))
    z80 = 1.2815515655446004
    probability_positive = normal_cdf(mean / max(standard_error, EPSILON))
    return {
        "effect": mean,
        "lower80": mean - z80 * standard_error,
        "upper80": mean + z80 * standard_error,
        "standard_error": standard_error,
        "probability_positive": probability_positive,
    }


def build_halo(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    validate_columns(frame, config)
    frame = prepare_frame(frame, config)
    design = build_design(frame, config)
    fits = {
        destination: fit_destination(frame, config, design, destination)
        for destination in config["destinations"]
    }
    geos = list(frame[config["geo_column"]].drop_duplicates())
    views = ["Total", *geos]
    relative_change = float(config["scenario"]["relative_change"])
    output_views: dict[str, Any] = {}

    for view in views:
        geo = None if view == "Total" else view
        mask = scenario_mask(frame, config, geo)
        cells: dict[str, Any] = {}
        row_totals = {channel: 0.0 for channel in config["channels"]}
        for channel in config["channels"]:
            delta_rows = counterfactual_delta(
                frame, config, design, channel, relative_change, mask
            )
            delta = delta_rows[mask].sum(axis=0)
            calibrated_destinations = {
                item["destination"]
                for item in config.get("experiments", [])
                if item["channel"] == channel
                and (not item.get("geo") or geo is None or item.get("geo") == geo)
            }
            for destination, fit in fits.items():
                cell = summarize_cell(delta, fit)
                cell["calibrated"] = destination in calibrated_destinations
                cells[f"{channel}|{destination}"] = cell
                row_totals[channel] += cell["effect"]
        output_views[view] = {
            "cells": cells,
            "row_totals": row_totals,
            "rows": int(mask.sum()),
        }

    diagnostics = {
        destination: {
            "r_squared": fit["r_squared"],
            "experiment_constraints": fit["experiment_count"],
        }
        for destination, fit in fits.items()
    }
    experiments = config.get("experiments", [])
    experiment_count = len(experiments)
    calibrated_pairs = {
        (item["channel"], item["destination"]) for item in experiments
    }
    required_pairs = {
        (channel, destination)
        for channel in config["channels"]
        for destination in config["destinations"]
    }
    if not calibrated_pairs:
        status = "observational_candidate"
        warning = "No randomized experiment constraints were supplied. These cells are model-implied candidates, not causal estimates."
    elif required_pairs.issubset(calibrated_pairs):
        status = "experiment_calibrated"
        warning = None
    else:
        status = "partially_calibrated"
        warning = "Only cells backed by randomized experiment constraints are publishable. Remaining observational cells are withheld."
    return {
        "schema_version": 1,
        "status": status,
        "warning": warning,
        "metadata": {
            "date_min": frame[config["date_column"]].min().date().isoformat(),
            "date_max": frame[config["date_column"]].max().date().isoformat(),
            "geographies": geos,
            "row_count": len(frame),
            "scenario": config["scenario"],
            "experiment_count": experiment_count,
            "method": "hierarchical Bayesian distributed-lag halo model",
            "measure": config.get("measure", "orders"),
        },
        "channels": list(config["channels"]),
        "destinations": list(config["destinations"]),
        "missing_levers": [
            channel for channel in config.get("expected_channels", config["channels"])
            if channel not in config["channels"]
        ],
        "views": output_views,
        "diagnostics": diagnostics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Geo-time panel CSV")
    parser.add_argument("--config", required=True, help="Model configuration JSON")
    parser.add_argument("--output", required=True, help="Output halo JSON")
    args = parser.parse_args()

    with open(args.config, encoding="utf8") as handle:
        config = json.load(handle)
    frame = pd.read_csv(args.input)
    result = build_halo(frame, config)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf8")
    print(
        f"Wrote {len(result['channels'])}x{len(result['destinations'])} halo matrix "
        f"({result['status']}) to {output_path}"
    )


if __name__ == "__main__":
    main()
