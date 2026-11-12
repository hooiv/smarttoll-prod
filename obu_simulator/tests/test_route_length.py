"""The README quotes the seeded driving trace, not a separate road distance."""

from pathlib import Path

import obu_simulator


def test_readme_matches_seeded_trace_length():
    length_km = round(obu_simulator._ROUTE_LENGTH / 1000.0, 1)
    assert length_km == 97.5
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
    assert "97.5 km" in readme
    assert "113 km" not in readme
