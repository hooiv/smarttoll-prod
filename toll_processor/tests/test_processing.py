import time
import pytest
from unittest.mock import MagicMock, patch, call

# Import the functions/classes to test
from app import processing
from app.models import GpsData, VehicleState, TollEvent
from app.config import settings

# Use pytest-mock fixture 'mocker' for convenience
pytest_plugins = ("pytest_mock",)

# --- Test Data ---
SAMPLE_GPS_INSIDE_ZONE = GpsData(
    deviceId="DEV123", vehicleId="VEH_ABC", timestamp=int(time.time() * 1000),
    latitude=40.710, longitude=-74.005, speedKmph=50.0
)
SAMPLE_GPS_OUTSIDE_ZONE = GpsData(
    deviceId="DEV123", vehicleId="VEH_ABC", timestamp=int(time.time() * 1000 + 5000),  # 5s later
    latitude=40.720, longitude=-74.000, speedKmph=60.0
)
SAMPLE_GPS_DIFFERENT_ZONE = GpsData(
    deviceId="DEV123", vehicleId="VEH_ABC", timestamp=int(time.time() * 1000 + 10000),  # 10s later
    latitude=40.730, longitude=-73.995, speedKmph=55.0
)

MOCK_ZONE_INFO_1 = {"zone_id": "ZoneA", "rate_per_km": 0.15}
MOCK_ZONE_INFO_2 = {"zone_id": "ZoneB", "rate_per_km": 0.20}

# --- Tests for calculate_distance_haversine ---

@pytest.mark.parametrize("lat1, lon1, lat2, lon2, expected_km", [
    (40.7128, -74.0060, 40.7128, -74.0060, 0.0),  # Same point
    (0.0, 0.0, 0.0, 1.0, pytest.approx(111.3, abs=0.2)),  # 1 degree longitude at equator
    (40.0, -75.0, 41.0, -75.0, pytest.approx(111.0, abs=0.5)),  # 1 degree latitude
    # Add more realistic test cases if needed
])
def test_calculate_distance_haversine(lat1, lon1, lat2, lon2, expected_km):
    distance = processing.calculate_distance_haversine(lat1, lon1, lat2, lon2)
    assert distance == expected_km

def test_calculate_distance_haversine_missing_coords():
    assert processing.calculate_distance_haversine(None, 0, 0, 0) == 0.0
    assert processing.calculate_distance_haversine(0, None, 0, 0) == 0.0
    assert processing.calculate_distance_haversine(0, 0, None, 0) == 0.0
    assert processing.calculate_distance_haversine(0, 0, 0, None) == 0.0

# --- Tests for process_gps_message ---

# Helper function to mock dependencies
@pytest.fixture
def mock_dependencies(mocker):
    """Mocks external dependencies for processing function."""
    # Mock functions from imported modules
    mock_get_state = mocker.patch("app.state.get_vehicle_state", return_value=None)
    mock_update_state = mocker.patch("app.state.update_vehicle_state")
    mock_get_zone = mocker.patch("app.database.get_current_toll_zone", return_value=None)
    mock_send_message = mocker.patch("app.kafka_client.send_message", return_value=True)
    mock_publish_error = mocker.patch("app.kafka_client.publish_error")

    # Mock distance calculation to return predictable value if needed
    mock_distance = mocker.patch("app.processing.calculate_distance_haversine", return_value=0.5)  # 0.5 km default

    return {
        "get_state": mock_get_state,
        "update_state": mock_update_state,
        "get_zone": mock_get_zone,
        "send_message": mock_send_message,
        "publish_error": mock_publish_error,
        "distance": mock_distance,
    }

def test_process_gps_message_invalid_data(mock_dependencies):
    """Test processing skips messages with invalid format."""
    invalid_message = {"deviceId": "DEV123", "vehicleId": "VEH_ABC"}  # Missing fields
    success = processing.process_gps_message(invalid_message, 100)
    assert success is True  # Should skip gracefully
    mock_dependencies["get_state"].assert_not_called()
    mock_dependencies["get_zone"].assert_not_called()
    mock_dependencies["publish_error"].assert_called_once()
    # Check that ValidationError was mentioned in the error message
    args, kwargs = mock_dependencies["publish_error"].call_args
    assert "ValidationError" in kwargs.get("error_type", "")
    assert "latitude" in kwargs.get("message", "")  # Error should mention missing latitude

def test_process_gps_message_entry_into_zone(mock_dependencies):
    """Test logic when a vehicle enters a toll zone."""
    mock_dependencies["get_state"].return_value = None  # Vehicle has no prior state
    mock_dependencies["get_zone"].return_value = MOCK_ZONE_INFO_1  # GPS is inside ZoneA

    success = processing.process_gps_message(SAMPLE_GPS_INSIDE_ZONE.model_dump(), 101)  # V2
    # success = processing.process_gps_message(SAMPLE_GPS_INSIDE_ZONE.dict(), 101)  # V1

    assert success is True
    mock_dependencies["get_state"].assert_called_once_with("VEH_ABC")
    mock_dependencies["get_zone"].assert_called_once_with(SAMPLE_GPS_INSIDE_ZONE.latitude, SAMPLE_GPS_INSIDE_ZONE.longitude)
    mock_dependencies["update_state"].assert_called_once()
    # Check the state being saved
    args, kwargs = mock_dependencies["update_state"].call_args
    assert args[0] == "VEH_ABC"  # vehicle_id
    saved_state: VehicleState = args[1]
    assert isinstance(saved_state, VehicleState)
    assert saved_state.in_zone is True
    assert saved_state.zone_id == "ZoneA"
    assert saved_state.rate_per_km == 0.15
    assert saved_state.distance_km == 0.0
    assert saved_state.lat == SAMPLE_GPS_INSIDE_ZONE.latitude
    assert saved_state.lon == SAMPLE_GPS_INSIDE_ZONE.longitude
    assert saved_state.entry_time == SAMPLE_GPS_INSIDE_ZONE.timestamp
    assert saved_state.deviceId == SAMPLE_GPS_INSIDE_ZONE.deviceId
    mock_dependencies["send_message"].assert_not_called()  # No toll event on entry

def test_process_gps_message_movement_within_zone(mock_dependencies):
    """Test logic when a vehicle moves within the same toll zone."""
    entry_time = SAMPLE_GPS_INSIDE_ZONE.timestamp
    prior_state = VehicleState(
        in_zone=True, zone_id="ZoneA", rate_per_km=0.15, entry_time=entry_time,
        distance_km=0.0, lat=SAMPLE_GPS_INSIDE_ZONE.latitude, lon=SAMPLE_GPS_INSIDE_ZONE.longitude,
        last_update=entry_time, deviceId="DEV123"
    )
    mock_dependencies["get_state"].return_value = prior_state
    mock_dependencies["get_zone"].return_value = MOCK_ZONE_INFO_1  # Still inside ZoneA

    # Simulate next GPS point slightly later inside the zone
    next_gps_data = SAMPLE_GPS_INSIDE_ZONE.model_copy(update={  # V2
        "timestamp": entry_time + 5000, "latitude": 40.711, "longitude": -74.006
    })
    # next_gps_data = SAMPLE_GPS_INSIDE_ZONE.copy(update={  # V1
    #     "timestamp": entry_time + 5000, "latitude": 40.711, "longitude": -74.006
    # })

    # Mock distance calculation for this specific movement
    mock_dependencies["distance"].return_value = 0.123  # km for this segment

    success = processing.process_gps_message(next_gps_data.model_dump(), 102)  # V2
    # success = processing.process_gps_message(next_gps_data.dict(), 102)  # V1

    assert success is True
    mock_dependencies["get_state"].assert_called_once_with("VEH_ABC")
    mock_dependencies["get_zone"].assert_called_once_with(next_gps_data.latitude, next_gps_data.longitude)
    mock_dependencies["update_state"].assert_called_once()
    # Check updated state
    args, kwargs = mock_dependencies["update_state"].call_args
    assert args[0] == "VEH_ABC"
    updated_state: VehicleState = args[1]
    assert updated_state.in_zone is True
    assert updated_state.zone_id == "ZoneA"
    assert updated_state.distance_km == pytest.approx(0.123)  # Accumulated distance
    assert updated_state.lat == next_gps_data.latitude  # Position updated
    assert updated_state.lon == next_gps_data.longitude
    assert updated_state.last_update == next_gps_data.timestamp
    mock_dependencies["send_message"].assert_not_called()  # No toll event yet

def test_process_gps_message_exit_from_zone(mock_dependencies):
    """Test logic when a vehicle exits a toll zone, generating a toll event."""
    entry_time = SAMPLE_GPS_INSIDE_ZONE.timestamp
    last_update_time = entry_time + 15000  # 15s after entry
    prior_state = VehicleState(
        in_zone=True, zone_id="ZoneA", rate_per_km=0.15, entry_time=entry_time,
        distance_km=1.25, lat=40.712, lon=-74.007,  # Last pos inside
        last_update=last_update_time, deviceId="DEV123"
    )
    mock_dependencies["get_state"].return_value = prior_state
    mock_dependencies["get_zone"].return_value = None  # Now outside any zone

    # Mock distance for the final segment (inside -> outside)
    mock_dependencies["distance"].return_value = 0.25  # km for the last segment

    success = processing.process_gps_message(SAMPLE_GPS_OUTSIDE_ZONE.model_dump(), 103)  # V2
    # success = processing.process_gps_message(SAMPLE_GPS_OUTSIDE_ZONE.dict(), 103)  # V1

    assert success is True
    mock_dependencies["get_state"].assert_called_once_with("VEH_ABC")
    mock_dependencies["get_zone"].assert_called_once_with(SAMPLE_GPS_OUTSIDE_ZONE.latitude, SAMPLE_GPS_OUTSIDE_ZONE.longitude)

    # Check state is cleared (update_state called with None)
    mock_dependencies["update_state"].assert_called_once_with("VEH_ABC", None)

    # Check that TollEvent is sent to Kafka
    mock_dependencies["send_message"].assert_called_once()
    args, kwargs = mock_dependencies["send_message"].call_args
    assert args[0] == settings.TOLL_EVENT_TOPIC  # Correct topic
    event_payload: dict = args[1]  # The message value
    assert isinstance(event_payload, dict)
    # Validate structure using Pydantic model (optional but good)
    toll_event = TollEvent(**event_payload)
    assert toll_event.vehicleId == "VEH_ABC"
    assert toll_event.deviceId == "DEV123"  # From state
    assert toll_event.zoneId == "ZoneA"
    assert toll_event.entryTime == entry_time
    assert toll_event.exitTime == SAMPLE_GPS_OUTSIDE_ZONE.timestamp
    assert toll_event.distanceKm == pytest.approx(1.25 + 0.25)  # Accumulated + final segment
    assert toll_event.ratePerKm == 0.15
    # Decimal ROUND_HALF_UP: 1.5 km * 0.15 $/km = 0.225 -> rounds to 0.23
    # (float gives 0.22 because 1.5*0.15 == 0.22499... due to representation error)
    assert toll_event.tollAmount == pytest.approx(0.23)
    assert toll_event.currency == "USD"

def test_process_gps_message_move_between_zones(mock_dependencies):
    """Test moving directly from one zone to another."""
    entry_time = SAMPLE_GPS_INSIDE_ZONE.timestamp
    last_update_time = entry_time + 15000  # 15s after entry
    prior_state = VehicleState(
        in_zone=True, zone_id="ZoneA", rate_per_km=0.15, entry_time=entry_time,
        distance_km=1.25, lat=40.712, lon=-74.007,  # Last pos inside ZoneA
        last_update=last_update_time, deviceId="DEV123"
    )
    mock_dependencies["get_state"].return_value = prior_state
    # This time, the new GPS point is inside ZoneB
    mock_dependencies["get_zone"].return_value = MOCK_ZONE_INFO_2

    # Mock distance for the segment ending ZoneA (inside A -> inside B)
    mock_dependencies["distance"].return_value = 0.30  # km for this segment

    success = processing.process_gps_message(SAMPLE_GPS_DIFFERENT_ZONE.model_dump(), 104)  # V2
    # success = processing.process_gps_message(SAMPLE_GPS_DIFFERENT_ZONE.dict(), 104)  # V1

    assert success is True
    mock_dependencies["get_state"].assert_called_once_with("VEH_ABC")
    mock_dependencies["get_zone"].assert_called_once_with(SAMPLE_GPS_DIFFERENT_ZONE.latitude, SAMPLE_GPS_DIFFERENT_ZONE.longitude)

    # Check that a TollEvent for ZoneA is sent and state is updated twice
    # (once to None clearing old zone, once with new ZoneB state)
    assert mock_dependencies["send_message"].call_count == 1
    assert mock_dependencies["update_state"].call_count == 2

    # First call must clear the old zone state
    first_update_args = mock_dependencies["update_state"].call_args_list[0][0]
    assert first_update_args[0] == "VEH_ABC"
    assert first_update_args[1] is None

    # --- Verify Toll Event (Exit from ZoneA) ---
    send_args, send_kwargs = mock_dependencies["send_message"].call_args
    assert send_args[0] == settings.TOLL_EVENT_TOPIC
    event_payload = send_args[1]
    toll_event_a = TollEvent(**event_payload)
    assert toll_event_a.zoneId == "ZoneA"
    assert toll_event_a.exitTime == SAMPLE_GPS_DIFFERENT_ZONE.timestamp  # Exit time is when new zone detected
    assert toll_event_a.distanceKm == pytest.approx(1.25 + 0.30)  # Accumulated + transition segment
    assert toll_event_a.ratePerKm == 0.15
    expected_toll_a = (1.25 + 0.30) * 0.15
    assert toll_event_a.tollAmount == pytest.approx(round(expected_toll_a, 2))

    # --- Verify New State (Entry into ZoneB) ---
    update_args, update_kwargs = mock_dependencies["update_state"].call_args
    assert update_args[0] == "VEH_ABC"
    new_state_b: VehicleState = update_args[1]
    assert isinstance(new_state_b, VehicleState)
    assert new_state_b.in_zone is True
    assert new_state_b.zone_id == "ZoneB"
    assert new_state_b.rate_per_km == 0.20
    assert new_state_b.distance_km == 0.0  # Distance resets on new zone entry
    assert new_state_b.lat == SAMPLE_GPS_DIFFERENT_ZONE.latitude
    assert new_state_b.lon == SAMPLE_GPS_DIFFERENT_ZONE.longitude
    assert new_state_b.entry_time == SAMPLE_GPS_DIFFERENT_ZONE.timestamp  # Entry time is current time
    assert new_state_b.deviceId == "DEV123"  # Should carry over deviceId

# --- Tests for GpsData timestamp staleness validation ---

def test_gps_data_accepts_current_timestamp():
    """GpsData accepts a timestamp that is current (now)."""
    gps = GpsData(
        deviceId="DEV1", vehicleId="VEH1",
        timestamp=int(time.time() * 1000),
        latitude=40.71, longitude=-74.0,
    )
    assert gps.timestamp > 0


def test_gps_data_accepts_recent_past_timestamp():
    """GpsData accepts a timestamp that is 5 minutes ago (within the 10-min window)."""
    five_min_ago_ms = int((time.time() - 5 * 60) * 1000)
    gps = GpsData(
        deviceId="DEV1", vehicleId="VEH1",
        timestamp=five_min_ago_ms,
        latitude=40.71, longitude=-74.0,
    )
    assert gps.timestamp == five_min_ago_ms


def test_gps_data_rejects_stale_timestamp():
    """GpsData rejects a timestamp older than 10 minutes."""
    from pydantic import ValidationError as PydanticValidationError
    stale_ms = int((time.time() - 11 * 60) * 1000)  # 11 minutes ago
    with pytest.raises(PydanticValidationError, match="too old"):
        GpsData(
            deviceId="DEV1", vehicleId="VEH1",
            timestamp=stale_ms,
            latitude=40.71, longitude=-74.0,
        )


def test_gps_data_rejects_far_future_timestamp():
    """GpsData rejects a timestamp more than 60 seconds in the future."""
    from pydantic import ValidationError as PydanticValidationError
    future_ms = int((time.time() + 120) * 1000)  # 2 minutes ahead
    with pytest.raises(PydanticValidationError, match="future"):
        GpsData(
            deviceId="DEV1", vehicleId="VEH1",
            timestamp=future_ms,
            latitude=40.71, longitude=-74.0,
        )
