"""Deterministic recovery checks for the halo engine."""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from halo_model import build_halo, geometric_adstock, hill


def synthetic_panel() -> tuple[pd.DataFrame, dict, dict[str, float]]:
    rng = np.random.default_rng(73)
    geos = [f"G{number}" for number in range(6)]
    days = pd.date_range("2025-01-01", periods=280, freq="D")
    rows = []
    true = {"Meta|Email": 18.0, "Meta|Direct": 7.0, "TV|Email": 4.0, "TV|Direct": 16.0}

    for geo_index, geo in enumerate(geos):
        meta = rng.gamma(4.0, 20.0, len(days)) * (1.0 + 0.05 * geo_index)
        tv = rng.gamma(2.0, 15.0, len(days)) * (1.0 - 0.03 * geo_index)
        meta_t = hill(geometric_adstock(meta, 1.0), np.median(geometric_adstock(meta, 1.0)), 1.0)
        tv_t = hill(geometric_adstock(tv, 2.0), np.median(geometric_adstock(tv, 2.0)), 1.0)
        seasonal = 10.0 * np.sin(2.0 * np.pi * np.arange(len(days)) / 365.25)
        for index, day in enumerate(days):
            baseline = 100.0 + 3.0 * geo_index + seasonal[index]
            rows.append({
                "date": day,
                "geo": geo,
                "promo": float((index % 29) < 4),
                "meta": meta[index],
                "tv": tv[index],
                "email": baseline + 18.0 * meta_t[index] + 4.0 * tv_t[index] + rng.normal(0, 2.0),
                "direct": 0.7 * baseline + 7.0 * meta_t[index] + 16.0 * tv_t[index] + rng.normal(0, 2.0),
            })

    config = {
        "date_column": "date",
        "geo_column": "geo",
        "periods_per_year": 365,
        "scenario": {"name": "20% reduction", "relative_change": -0.2, "periods": 90},
        "controls": ["promo"],
        "channels": {
            "Meta": {"column": "meta", "half_life_periods": 1.0, "slope": 1.0},
            "TV": {"column": "tv", "half_life_periods": 2.0, "slope": 1.0},
        },
        "destinations": {"Email": "email", "Direct": "direct"},
        "priors": {
            "baseline_sd": 10.0,
            "control_sd": 2.0,
            "media_sd": 2.0,
            "media_geo_deviation_sd": 0.2,
        },
        "experiments": [],
    }
    return pd.DataFrame(rows), config, true


def test_signal_recovery() -> None:
    frame, config, _ = synthetic_panel()
    result = build_halo(frame, config)
    cells = result["views"]["Total"]["cells"]
    for key in ("Meta|Email", "Meta|Direct", "TV|Email", "TV|Direct"):
        assert cells[key]["effect"] > 0, (key, cells[key])
        assert cells[key]["probability_positive"] > 0.95, (key, cells[key])
    assert cells["Meta|Email"]["effect"] > cells["Meta|Direct"]["effect"]
    assert cells["TV|Direct"]["effect"] > cells["TV|Email"]["effect"]


def test_experiment_calibration_moves_posterior() -> None:
    frame, config, _ = synthetic_panel()
    uncalibrated = build_halo(frame, config)["views"]["Total"]["cells"]["TV|Email"]
    calibrated_config = copy.deepcopy(config)
    calibrated_config["experiments"] = [{
        "channel": "TV",
        "destination": "Email",
        "start": "2025-07-10",
        "end": "2025-10-07",
        "relative_change": -0.2,
        "effect": -120.0,
        "standard_error": 8.0,
    }]
    calibrated = build_halo(frame, calibrated_config)["views"]["Total"]["cells"]["TV|Email"]
    assert calibrated["calibrated"] is True
    assert calibrated["effect"] > uncalibrated["effect"]
    assert calibrated["standard_error"] < uncalibrated["standard_error"]


if __name__ == "__main__":
    test_signal_recovery()
    test_experiment_calibration_moves_posterior()
    print("halo_model: all recovery checks passed")
