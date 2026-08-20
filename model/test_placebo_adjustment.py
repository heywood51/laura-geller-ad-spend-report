"""Recovery checks for the empirical-null halo correction."""

from validate_placebos import adjust_model, benjamini_hochberg


def cell(effect: float) -> dict:
    return {
        "effect": effect,
        "lower80": effect - 1.0,
        "upper80": effect + 1.0,
        "standard_error": 1.0,
        "probability_positive": 0.5,
        "calibrated": False,
    }


def test_benjamini_hochberg_is_monotone() -> None:
    q = benjamini_hochberg({"a": 0.001, "b": 0.02, "c": 0.5})
    assert q["a"] <= q["b"] <= q["c"]


def test_adjustment_keeps_only_signal_beyond_empirical_null() -> None:
    model = {
        "status": "observational_candidate",
        "warning": "test",
        "metadata": {"method": "test"},
        "channels": ["Source"],
        "destinations": ["Strong", "Weak"],
        "views": {"Total": {
            "cells": {"Source|Strong": cell(10.0), "Source|Weak": cell(0.5)},
            "row_totals": {"Source": 10.5},
        }},
    }
    null = [-1.0, 0.0, 1.0] * 20
    placebos = {"Total": {"Source|Strong": null, "Source|Weak": null}}
    adjusted = adjust_model(model, placebos, 0.05)
    cells = adjusted["views"]["Total"]["cells"]
    assert cells["Source|Strong"]["passes_placebo"] is True
    assert cells["Source|Strong"]["effect"] == 9.0
    assert cells["Source|Weak"]["passes_placebo"] is False
    assert cells["Source|Weak"]["effect"] == 0.0


if __name__ == "__main__":
    test_benjamini_hochberg_is_monotone()
    test_adjustment_keeps_only_signal_beyond_empirical_null()
    print("placebo_adjustment: all recovery checks passed")
