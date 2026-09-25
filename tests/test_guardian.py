"""
test_guardian.py
Automated regression tests for OT Guardian's runtime behaviour.

These replace the manual, print-based "PASS/FAIL" checks that were run
by hand inside the deployment notebook with real, repeatable pytest
assertions against the actual shipped `src/guardian.py` module — so a
future change to the code gets checked automatically instead of by eye.

Prerequisites:
    1. `numpy` and `onnxruntime` installed (see requirements.txt).
    2. `models/guardian_autoencoder.onnx` present, since importing
       `src.guardian` loads the ONNX Runtime session immediately.
    3. Run from the project root so `src` resolves as a package:

        pytest test_guardian.py -v
"""

import pytest

from src.guardian import analyze_event, guardian_threshold


# ======================================================================
# TEST 1 — KNOWN NORMAL EVENT
# ======================================================================

def test_known_normal_event_is_normal():
    event = {
        "source": "PLC-01",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    }

    result = analyze_event(event)["result"]

    assert result["status"] == "NORMAL"
    assert result["ai_suspicious"] is False
    assert result["context_evidence"] == []


# ======================================================================
# TEST 2 — REVERSE DIRECTION
# ======================================================================

def test_reverse_direction_is_suspicious():
    event = {
        "source": "HIST-01",
        "destination": "PLC-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    }

    result = analyze_event(event)["result"]

    assert result["status"] == "SUSPICIOUS"
    assert result["context"]["direction_known"] is False


# ======================================================================
# TEST 3 — NEW INFORMATION TYPE FOR A KNOWN DIRECTION
# ======================================================================

def test_new_information_type_is_suspicious():
    event = {
        "source": "PLC-01",
        "destination": "HIST-01",
        "information": "process_status",
        "protocol": "OPC-UA",
        "port": 4840,
    }

    result = analyze_event(event)["result"]

    assert result["status"] == "SUSPICIOUS"
    assert result["context_evidence"] != []


# ======================================================================
# TEST 4 — NEW PROTOCOL FOR A KNOWN RELATIONSHIP
# ======================================================================

def test_new_protocol_is_suspicious():
    event = {
        "source": "PLC-01",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "Modbus/TCP",
        "port": 502,
    }

    result = analyze_event(event)["result"]

    assert result["status"] == "SUSPICIOUS"


# ======================================================================
# TEST 5 — COMPLETELY NEW DEVICE RELATIONSHIP
# ======================================================================

def test_new_relationship_is_suspicious():
    event = {
        "source": "HMI-01",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    }

    result = analyze_event(event)["result"]

    assert result["status"] == "SUSPICIOUS"
    assert result["context"]["relationship_known"] is False


# ======================================================================
# TEST 6 — KNOWN INFORMATION TYPE IN A NEW CONTEXT
# ======================================================================

def test_known_information_in_new_context_is_suspicious():
    event = {
        "source": "PLC-02",
        "destination": "HIST-01",
        "information": "process_read",
        "protocol": "OPC-UA",
        "port": 4840,
    }

    result = analyze_event(event)["result"]

    assert result["status"] == "SUSPICIOUS"
    assert result["context"]["relationship_known"] is True
    assert result["context"]["information_known_for_direction"] is False


# ======================================================================
# TEST 7 — UNKNOWN SOURCE DEVICE
# ======================================================================

def test_unknown_source_device_is_suspicious():
    event = {
        "source": "NEW-DEVICE",
        "destination": "PLC-01",
        "information": "process_status",
        "protocol": "Modbus/TCP",
        "port": 502,
    }

    result = analyze_event(event)["result"]

    assert result["status"] == "SUSPICIOUS"
    assert result["ai_suspicious"] is True
    assert "Source device is unknown" in result["context_evidence"]


# ======================================================================
# TEST 8 — UNKNOWN DESTINATION DEVICE
# ======================================================================

def test_unknown_destination_device_is_suspicious():
    event = {
        "source": "PLC-01",
        "destination": "NEW-DEVICE",
        "information": "process_status",
        "protocol": "Modbus/TCP",
        "port": 502,
    }

    result = analyze_event(event)["result"]

    assert result["status"] == "SUSPICIOUS"
    assert "Destination device is unknown" in result["context_evidence"]


# ======================================================================
# TEST 9 — MULTIPLE SIMULTANEOUS ANOMALIES
# ======================================================================

def test_multiple_anomalies_are_all_detected():
    event = {
        "source": "NEW-DEVICE",
        "destination": "PLC-01",
        "information": "process_status",
        "protocol": "Modbus/TCP",
        "port": 502,
        "timestamp": 500,
        "bytes": 5000,
    }

    result = analyze_event(event)["result"]

    assert result["status"] == "SUSPICIOUS"
    assert result["ai_suspicious"] is True
    assert result["context_evidence"] != []
    assert result["timing_evidence"] != []
    assert result["volume_evidence"] != []


# ======================================================================
# TEST 10 — TEMPORAL CHECK: UNUSUAL TIME GAP
# ======================================================================

def test_unusual_time_gap_is_flagged():
    event = {
        "source": "PLC-01",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
        "timestamp": 500,
    }

    result = analyze_event(event)["result"]

    assert result["timing_evidence"] != []


# ======================================================================
# TEST 11 — VOLUME CHECK: UNUSUALLY LARGE MESSAGE
# ======================================================================

def test_unusually_large_volume_is_flagged():
    event = {
        "source": "PLC-01",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
        "bytes": 5000,
    }

    result = analyze_event(event)["result"]

    assert result["volume_evidence"] != []


# ======================================================================
# TEST 12 — VOLUME CHECK: UNUSUALLY SMALL MESSAGE
# ======================================================================

def test_unusually_small_volume_is_flagged():
    event = {
        "source": "PLC-01",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
        "bytes": 10,
    }

    result = analyze_event(event)["result"]

    assert result["volume_evidence"] != []


# ======================================================================
# TEST 13 — SAFETY BOUNDARY: RESULT NEVER CARRIES AN ACTION
# ======================================================================

def test_analyze_event_only_returns_result_and_explanation():
    event = {
        "source": "HIST-01",
        "destination": "PLC-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    }

    outcome = analyze_event(event)

    assert set(outcome.keys()) == {"result", "explanation"}
    assert isinstance(outcome["explanation"], str)


# ======================================================================
# TEST 14 — THRESHOLD SANITY CHECK
# ======================================================================

def test_guardian_threshold_matches_validated_value():
    assert guardian_threshold == pytest.approx(0.0010467613755015663)
