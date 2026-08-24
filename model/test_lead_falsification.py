"""Recovery checks for the directed reverse-causality gate."""

from validate_placebos import apply_lead_falsification


def model(effect: float, passes: bool = True) -> dict:
    return {
        "metadata": {"method": "test"},
        "warning": "test",
        "channels": ["Source"],
        "destinations": ["Outcome"],
        "views": {"Total": {
            "cells": {"Source|Outcome": {
                "effect": effect,
                "raw_effect": effect,
                "lower80": effect - 2,
                "upper80": effect + 2,
                "standard_error": 1,
                "probability_positive": 0.99,
                "passes_placebo": passes,
                "placebo_bias": 0,
            }},
            "row_totals": {"Source": effect},
        }},
    }


def lead_models(*effects: float) -> dict:
    return {
        lead: {"Source": model(effect)}
        for lead, effect in zip((1, 2, 3), effects)
    }


def test_future_exposure_that_is_weaker_passes() -> None:
    result = apply_lead_falsification(
        model(10), model(10), lead_models(4, 2, 1), (1, 2, 3)
    )
    cell = result["views"]["Total"]["cells"]["Source|Outcome"]
    assert cell["passes_lead_falsification"] is True
    assert cell["passes_validation"] is True
    assert cell["effect"] == 10


def test_future_exposure_that_is_as_strong_is_rejected() -> None:
    result = apply_lead_falsification(
        model(10), model(10), lead_models(11, 3, 1), (1, 2, 3)
    )
    cell = result["views"]["Total"]["cells"]["Source|Outcome"]
    assert cell["passes_lead_falsification"] is False
    assert cell["passes_validation"] is False
    assert cell["passes_empirical_null"] is True
    assert cell["effect"] == 0
    assert result["views"]["Total"]["row_totals"]["Source"] == 0


if __name__ == "__main__":
    test_future_exposure_that_is_weaker_passes()
    test_future_exposure_that_is_as_strong_is_rejected()
    print("lead_falsification: all recovery checks passed")
