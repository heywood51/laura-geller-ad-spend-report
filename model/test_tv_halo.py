"""Basic integrity checks for the published TV diagnostic."""

import json
from pathlib import Path


def test_tv_diagnostic_is_structurally_off_diagonal() -> None:
    path = Path(__file__).parent / "generated" / "tv-halo-diagnostic.json"
    diagnostic = json.loads(path.read_text(encoding="utf8"))
    for measure in ("orders", "revenue"):
        result = diagnostic[measure]
        assert result["candidate_destination_routing"]["Television"] == 0
        assert abs(sum(result["candidate_destination_routing"].values()) - max(0, result["candidate_effect"])) < 1e-6
        assert result["published_effect"] == (result["candidate_effect"] if result["publishable"] else 0)
        assert 0 <= result["time_placebo_empirical_p"] <= 1


if __name__ == "__main__":
    test_tv_diagnostic_is_structurally_off_diagonal()
    print("tv_halo: all diagnostic checks passed")
