"""TV-specific synthetic-control and intensity-response diagnostic.

TV appears only in the United States and is always on. This estimator therefore
uses non-US outcomes, US non-TV media, promotions, calendar terms and trend as
controls, then measures the association between residual US outcomes and
residual TV intensity across a pre-specified half-life ensemble. It publishes
only when block-bootstrap, time-placebo and lead falsification checks all pass.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from halo_model import geometric_adstock, hill


HALF_LIVES = (1, 3, 7, 14, 21, 28)
RIDGE = 10.0
BLOCK = 14


def residualizer(frame: pd.DataFrame, config: dict, outcome_columns: list[str]):
    us = frame[frame[config["geo_column"]].eq("United States")].sort_values("date").reset_index(drop=True)
    n = len(us)
    time = np.arange(n, dtype=float)
    controls = [time / max(time.max(), 1), (time / max(time.max(), 1)) ** 2]
    for harmonic in (1, 2, 3, 4):
        angle = 2 * np.pi * harmonic * time / 365.25
        controls.extend([np.sin(angle), np.cos(angle)])
    for weekday in range(6):
        controls.append(us["date"].dt.dayofweek.eq(weekday).to_numpy(float))
    for name in config.get("controls", []):
        controls.append(us[name].to_numpy(float))
    for channel, settings in config["channels"].items():
        if channel != "Television":
            controls.append(np.log1p(np.maximum(us[settings["column"]].to_numpy(float), 0)))
    for geo in sorted(set(frame[config["geo_column"]]) - {"United States"}):
        donor = frame[frame[config["geo_column"]].eq(geo)].sort_values("date")
        donor_total = donor[outcome_columns].sum(axis=1).to_numpy(float)
        controls.append(np.log1p(np.maximum(donor_total, 0)))
    x = np.column_stack(controls)
    scales = np.where(x.std(axis=0) > 1e-9, x.std(axis=0), 1.0)
    x = (x - x.mean(axis=0)) / scales
    x = np.column_stack([np.ones(n), x])
    penalty = RIDGE * np.eye(x.shape[1])
    penalty[0, 0] = 0
    projection = np.linalg.solve(x.T @ x + penalty, x.T)
    return us, lambda values: values - x @ (projection @ values)


def transformed_tv(spend: np.ndarray, half_life: float) -> tuple[np.ndarray, np.ndarray, float]:
    stocked = geometric_adstock(spend, half_life)
    midpoint = float(np.median(stocked[stocked > 0]))
    observed = hill(stocked, midpoint, 1.0)
    reduced = hill(geometric_adstock(spend * 0.8, half_life), midpoint, 1.0)
    return observed, reduced, float(np.sum((observed - reduced)[-365:]))


def coefficient_effect(y_residual: np.ndarray, z_residual: np.ndarray, delta: float) -> float:
    denominator = float(z_residual @ z_residual)
    return float(z_residual @ y_residual / denominator) * delta if denominator > 1e-12 else 0.0


def analyze_measure(frame: pd.DataFrame, config: dict, seed: int = 20260824) -> dict:
    destination_columns = list(config["destinations"].values())
    us, residualize = residualizer(frame, config, destination_columns)
    spend = np.maximum(us[config["channels"]["Television"]["column"]].to_numpy(float), 0)
    transformed = {half: transformed_tv(spend, half) for half in HALF_LIVES}
    total_y = us[destination_columns].sum(axis=1).to_numpy(float)
    y_residual = residualize(total_y)
    z_residuals = {half: residualize(values[0]) for half, values in transformed.items()}
    effects = {
        half: coefficient_effect(y_residual, z_residuals[half], transformed[half][2])
        for half in HALF_LIVES
    }
    candidate = float(np.median(list(effects.values())))
    stability = float(np.mean(np.asarray(list(effects.values())) > 0))

    rng = np.random.default_rng(seed)
    bootstrap = []
    n = len(us)
    blocks_needed = int(np.ceil(n / BLOCK))
    for _ in range(500):
        starts = rng.integers(0, n - BLOCK + 1, size=blocks_needed)
        index = np.concatenate([np.arange(start, start + BLOCK) for start in starts])[:n]
        estimates = [
            coefficient_effect(y_residual[index], z_residuals[half][index], transformed[half][2])
            for half in HALF_LIVES
        ]
        bootstrap.append(float(np.median(estimates)))
    lower80, upper80 = np.quantile(bootstrap, [0.1, 0.9])

    offsets = np.linspace(45, n - 45, 100, dtype=int)
    placebo = []
    for offset in offsets:
        shifted = []
        for half in HALF_LIVES:
            residual = residualize(np.roll(transformed[half][0], int(offset)))
            shifted.append(coefficient_effect(y_residual, residual, transformed[half][2]))
        placebo.append(float(np.median(shifted)))
    empirical_p = float((1 + np.sum(np.abs(placebo) >= abs(candidate))) / (len(placebo) + 1))
    placebo_p95 = float(np.quantile(np.abs(placebo), 0.95))

    lead_effects = {}
    for lead in (7, 14, 21, 28):
        estimates = []
        for half in HALF_LIVES:
            future_tv = residualize(np.roll(transformed[half][0], -lead))
            estimates.append(coefficient_effect(y_residual, future_tv, transformed[half][2]))
        lead_effects[str(lead)] = float(np.median(estimates))
    max_abs_lead = max(abs(value) for value in lead_effects.values())
    publishable = bool(
        candidate > 0
        and lower80 > 0
        and stability >= 0.8
        and empirical_p <= 0.05
        and abs(candidate) > max_abs_lead
    )

    destination_candidates = {}
    for destination, column in config["destinations"].items():
        if destination == "Television":
            destination_candidates[destination] = 0.0
            continue
        residual = residualize(us[column].to_numpy(float))
        estimates = [
            coefficient_effect(residual, z_residuals[half], transformed[half][2])
            for half in HALF_LIVES
        ]
        destination_candidates[destination] = max(0.0, float(np.median(estimates)))
    route_sum = sum(destination_candidates.values())
    if route_sum and candidate > 0:
        destination_candidates = {
            destination: candidate * value / route_sum
            for destination, value in destination_candidates.items()
        }
    else:
        destination_candidates = {destination: 0.0 for destination in destination_candidates}

    failed = []
    if lower80 <= 0:
        failed.append("block_bootstrap_interval")
    if stability < 0.8:
        failed.append("half_life_stability")
    if empirical_p > 0.05:
        failed.append("time_placebo")
    if abs(candidate) <= max_abs_lead:
        failed.append("lead_falsification")
    return {
        "measure": config["measure"],
        "candidate_effect": candidate,
        "published_effect": candidate if publishable else 0.0,
        "publishable": publishable,
        "lower80": float(lower80),
        "upper80": float(upper80),
        "positive_half_life_share": stability,
        "effects_by_half_life": {str(key): value for key, value in effects.items()},
        "time_placebo_empirical_p": empirical_p,
        "time_placebo_abs_p95": placebo_p95,
        "lead_effects": lead_effects,
        "failed_gates": failed,
        "candidate_destination_routing": destination_candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--orders-config", required=True)
    parser.add_argument("--revenue-config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    frame = pd.read_csv(args.input, parse_dates=["date"])
    with open(args.orders_config, encoding="utf8") as handle:
        orders_config = json.load(handle)
    with open(args.revenue_config, encoding="utf8") as handle:
        revenue_config = json.load(handle)
    result = {
        "status": "tv_specific_observational_diagnostic",
        "method": "US residual intensity response with non-US donor outcomes, half-life ensemble, block bootstrap, time placebos and lead falsification",
        "data_fact": "TV spend is US-only and present on every observed day; identification comes from intensity changes, not on/off or geo treatment variation.",
        "orders": analyze_measure(frame, orders_config),
        "revenue": analyze_measure(frame, revenue_config, seed=20260825),
    }
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
