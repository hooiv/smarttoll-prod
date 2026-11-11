from app import tracks


def test_record_keeps_latest_points_for_a_vehicle():
    tracks.record("VEH_A", 40.71, -74.005, 1_000, True)
    tracks.record("VEH_A", 40.712, -74.004, 2_000, True)
    snapshot = {item["vehicleId"]: item["points"] for item in tracks.snapshot()}
    assert snapshot["VEH_A"][-1]["lat"] == 40.712
    assert snapshot["VEH_A"][-1]["inZone"] is True
    assert len(snapshot["VEH_A"]) == 2
