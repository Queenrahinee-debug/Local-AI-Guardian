"""
OT Guardian v0.9
Local OT/ICS behavioural security monitor.

Runtime responsibilities:
    1. Encode an OT communication event into the original 18-feature vector.
    2. Run the deployed autoencoder through ONNX Runtime.
    3. Calculate reconstruction error.
    4. Investigate communication context.
    5. Investigate temporal behaviour.
    6. Investigate communication volume.
    7. Fuse AI + investigation evidence.
    8. Return a structured Guardian result.

Safety boundary:
    - Observe: YES
    - Analyze: YES
    - Investigate: YES
    - Explain: YES
    - Alert: YES
    - Block traffic: NO
    - Modify PLC: NO
    - Change process: NO
    - Shutdown: NO
    - Control OT: NO
"""

from pathlib import Path

import numpy as np
import onnxruntime as ort


# ======================================================================
# PATHS
# ======================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "guardian_autoencoder.onnx"
)


# ======================================================================
# ORIGINAL v0.9 NORMAL BASELINE
# ======================================================================

normal_events = [

    {
        "source": "HMI-01",
        "destination": "PLC-01",
        "information": "process_read",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "HMI-01",
        "destination": "PLC-01",
        "information": "process_read",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "HMI-01",
        "destination": "PLC-02",
        "information": "process_read",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "PLC-01",
        "destination": "HMI-01",
        "information": "process_status",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "PLC-01",
        "destination": "HMI-01",
        "information": "process_status",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "PLC-02",
        "destination": "HMI-01",
        "information": "process_status",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "PLC-01",
        "destination": "PLC-02",
        "information": "controller_state",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "PLC-01",
        "destination": "PLC-02",
        "information": "controller_state",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "PLC-02",
        "destination": "PLC-01",
        "information": "controller_state",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "PLC-02",
        "destination": "PLC-01",
        "information": "controller_state",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "SCADA-01",
        "destination": "PLC-01",
        "information": "supervisory_command",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "PLC-01",
        "destination": "SCADA-01",
        "information": "process_status",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "PLC-01",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    },

    {
        "source": "PLC-01",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    },

    {
        "source": "PLC-01",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    },

    {
        "source": "PLC-01",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    },

    {
        "source": "PLC-02",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    },

    {
        "source": "PLC-02",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    },

    {
        "source": "PLC-02",
        "destination": "HIST-01",
        "information": "process_data",
        "protocol": "OPC-UA",
        "port": 4840,
    },

    {
        "source": "SIS-01",
        "destination": "SCADA-01",
        "information": "safety_status",
        "protocol": "Modbus/TCP",
        "port": 502,
    },

    {
        "source": "SIS-01",
        "destination": "SCADA-01",
        "information": "safety_status",
        "protocol": "Modbus/TCP",
        "port": 502,
    },
]


normal_timestamps = [
    0, 5, 10, 15, 20, 25,
    30, 35, 40, 45, 50, 55,
    65, 75, 85, 95, 105, 115,
    125, 135, 140,
]


normal_volumes = [
    180, 180, 180,
    160, 160, 160,
    140, 140, 140, 140,
    210, 190,
    820, 820, 820, 820, 820, 820, 820,
    120, 120,
]


# ======================================================================
# DEVICE MAP
# ======================================================================

devices = {

    "PLC-01": {
        "level": 1,
        "ip": "10.0.1.10",
    },

    "PLC-02": {
        "level": 1,
        "ip": "10.0.1.11",
    },

    "SIS-01": {
        "level": 1,
        "ip": "10.0.1.12",
    },

    "HMI-01": {
        "level": 2,
        "ip": "10.0.2.10",
    },

    "SCADA-01": {
        "level": 3,
        "ip": "10.0.3.10",
    },

    "HIST-01": {
        "level": 3.5,
        "ip": "10.0.35.10",
    },
}


# ======================================================================
# FEATURE VOCABULARIES
# ======================================================================

sources = sorted(
    set(event["source"] for event in normal_events)
)

destinations = sorted(
    set(event["destination"] for event in normal_events)
)

information_types = sorted(
    set(event["information"] for event in normal_events)
)

protocols = sorted(
    set(
        (event["protocol"], event["port"])
        for event in normal_events
    )
)


# ======================================================================
# FEATURE ENCODING
# ======================================================================

def one_hot(value, known_values):
    """
    Reproduce the original v0.9 one-hot encoding.

    Unknown values intentionally produce an all-zero vector for
    that feature group, matching the original implementation.
    """

    vector = []

    for item in known_values:

        if value == item:
            vector.append(1.0)

        else:
            vector.append(0.0)

    return vector


def event_to_features(event):
    """
    Convert one OT communication event into the original
    18-dimensional Guardian feature vector.
    """

    features = []

    features += one_hot(
        event["source"],
        sources,
    )

    features += one_hot(
        event["destination"],
        destinations,
    )

    features += one_hot(
        event["information"],
        information_types,
    )

    protocol_key = (
        event["protocol"],
        event["port"],
    )

    features += one_hot(
        protocol_key,
        protocols,
    )

    if len(features) != 18:
        raise ValueError(
            f"Guardian feature vector must contain 18 values, "
            f"got {len(features)}"
        )

    return features


# ======================================================================
# CONTEXT BASELINE
# ======================================================================

known_relationships = set()
known_directions = set()

known_information_by_direction = set()
known_protocols_by_direction = set()

known_information_types = set()
known_protocol_types = set()


for event in normal_events:

    source = event["source"]
    destination = event["destination"]

    relationship = frozenset(
        (source, destination)
    )

    direction = (
        source,
        destination,
    )

    information_key = (
        source,
        destination,
        event["information"],
    )

    protocol_key = (
        source,
        destination,
        event["protocol"],
        event["port"],
    )

    known_relationships.add(
        relationship
    )

    known_directions.add(
        direction
    )

    known_information_by_direction.add(
        information_key
    )

    known_protocols_by_direction.add(
        protocol_key
    )

    known_information_types.add(
        event["information"]
    )

    known_protocol_types.add(
        (
            event["protocol"],
            event["port"],
        )
    )


# ======================================================================
# TEMPORAL BASELINE
# ======================================================================

normal_time_gaps = []

for i in range(1, len(normal_timestamps)):

    gap = (
        normal_timestamps[i]
        - normal_timestamps[i - 1]
    )

    normal_time_gaps.append(gap)


average_time_gap = (
    sum(normal_time_gaps)
    / len(normal_time_gaps)
)

maximum_time_gap = max(
    normal_time_gaps
)

time_gap_threshold = (
    maximum_time_gap * 2
)


# ======================================================================
# VOLUME BASELINE
# ======================================================================

average_volume = (
    sum(normal_volumes)
    / len(normal_volumes)
)

minimum_volume = min(
    normal_volumes
)

maximum_volume = max(
    normal_volumes
)

volume_upper_threshold = (
    maximum_volume * 1.5
)

volume_lower_threshold = (
    minimum_volume * 0.5
)


# ======================================================================
# AI THRESHOLD
# ======================================================================
#
# This is the stored v0.9 threshold established during validation.
#
# It was:
#
# maximum training reconstruction error
#       × 1.5
#
# = 0.0010467613755015663
#
# We do NOT retrain or recalculate the model threshold at runtime.
# ======================================================================

guardian_threshold = 0.0010467613755015663


# ======================================================================
# ONNX RUNTIME
# ======================================================================

def _create_session():
    """
    Create the ONNX Runtime inference session.

    The runtime model is loaded once when the Guardian module starts.
    """

    if not MODEL_PATH.exists():

        raise FileNotFoundError(
            f"Guardian ONNX model not found: {MODEL_PATH}"
        )

    return ort.InferenceSession(
        str(MODEL_PATH),
        providers=["CPUExecutionProvider"],
    )


session = _create_session()


# ======================================================================
# AI RECONSTRUCTION ERROR
# ======================================================================

def guardian_reconstruction_error(event):
    """
    Run the deployed ONNX autoencoder and return reconstruction error.
    """

    features = event_to_features(event)

    x = np.asarray(
        [features],
        dtype=np.float32,
    )

    output = session.run(
        ["guardian_output"],
        {
            "guardian_input": x,
        },
    )[0]

    error = np.mean(
        (output - x) ** 2
    )

    return float(error)


# ======================================================================
# CONTEXT INVESTIGATION
# ======================================================================

def guardian_investigate_context(event):

    evidence = []

    source = event["source"]
    destination = event["destination"]

    relationship = frozenset(
        (source, destination)
    )

    direction = (
        source,
        destination,
    )

    reverse_direction = (
        destination,
        source,
    )

    information_key = (
        source,
        destination,
        event["information"],
    )

    protocol_key = (
        source,
        destination,
        event["protocol"],
        event["port"],
    )

    relationship_is_known = (
        relationship
        in known_relationships
    )

    direction_is_known = (
        direction
        in known_directions
    )

    # --------------------------------------------------------------
    # DEVICE CHECK
    # --------------------------------------------------------------

    if source not in devices:

        evidence.append(
            "Source device is unknown"
        )

    if destination not in devices:

        evidence.append(
            "Destination device is unknown"
        )

    # --------------------------------------------------------------
    # RELATIONSHIP + DIRECTION
    # --------------------------------------------------------------

    if not relationship_is_known:

        if reverse_direction in known_directions:

            evidence.append(
                "Known device pair communicating in a "
                "previously unseen direction"
            )

        else:

            evidence.append(
                "Previously unseen device relationship"
            )

    elif not direction_is_known:

        evidence.append(
            "Previously unseen communication direction "
            "for a known device relationship"
        )

    # --------------------------------------------------------------
    # INFORMATION CONTEXT
    # --------------------------------------------------------------

    if relationship_is_known and direction_is_known:

        if information_key not in known_information_by_direction:

            if event["information"] in known_information_types:

                evidence.append(
                    "Known information type used in a "
                    "new communication context"
                )

            else:

                evidence.append(
                    "Previously unseen information or "
                    "operation type for this communication"
                )

    # --------------------------------------------------------------
    # PROTOCOL CONTEXT
    # --------------------------------------------------------------

    if relationship_is_known and direction_is_known:

        if protocol_key not in known_protocols_by_direction:

            if (
                event["protocol"],
                event["port"],
            ) in known_protocol_types:

                evidence.append(
                    "Known protocol/port used in a "
                    "new communication context"
                )

            else:

                evidence.append(
                    "Previously unseen protocol or port "
                    "for this communication"
                )

    context = {

        "relationship_known":
            relationship_is_known,

        "direction_known":
            direction_is_known,

        "information_known_globally":
            event["information"]
            in known_information_types,

        "information_known_for_direction":
            information_key
            in known_information_by_direction,

        "protocol_known_globally":
            (
                event["protocol"],
                event["port"],
            )
            in known_protocol_types,

        "protocol_known_for_direction":
            protocol_key
            in known_protocols_by_direction,
    }

    return evidence, context


# ======================================================================
# TEMPORAL INVESTIGATION
# ======================================================================

def guardian_investigate_timing(event):

    evidence = []

    if "timestamp" not in event:
        return evidence

    timestamp = event["timestamp"]

    latest_normal_timestamp = (
        normal_timestamps[-1]
    )

    time_gap = (
        timestamp
        - latest_normal_timestamp
    )

    if time_gap < 0:

        evidence.append(
            "Event timestamp is earlier than the "
            "latest observed normal timestamp"
        )

    elif time_gap > time_gap_threshold:

        evidence.append(
            "Unusual time gap between observations"
        )

    return evidence


# ======================================================================
# VOLUME INVESTIGATION
# ======================================================================

def guardian_investigate_volume(event):

    evidence = []

    if "bytes" not in event:
        return evidence

    volume = event["bytes"]

    if volume > volume_upper_threshold:

        evidence.append(
            "Unusually large communication volume"
        )

    elif volume < volume_lower_threshold:

        evidence.append(
            "Unusually small communication volume"
        )

    return evidence


# ======================================================================
# FULL GUARDIAN ANALYSIS
# ======================================================================

def guardian_analyze(event):
    """
    Analyze one OT communication event.

    Final decision:
        SUSPICIOUS = AI anomaly OR investigation anomaly
        NORMAL     = neither detected
    """

    # --------------------------------------------------------------
    # AI
    # --------------------------------------------------------------

    score = guardian_reconstruction_error(event)

    ai_suspicious = (
        score > guardian_threshold
    )

    # --------------------------------------------------------------
    # Context
    # --------------------------------------------------------------

    context_evidence, context = (
        guardian_investigate_context(event)
    )

    # --------------------------------------------------------------
    # Temporal
    # --------------------------------------------------------------

    timing_evidence = (
        guardian_investigate_timing(event)
    )

    # --------------------------------------------------------------
    # Volume
    # --------------------------------------------------------------

    volume_evidence = (
        guardian_investigate_volume(event)
    )

    # --------------------------------------------------------------
    # Combine evidence
    # --------------------------------------------------------------

    evidence = []

    evidence += context_evidence
    evidence += timing_evidence
    evidence += volume_evidence

    investigation_anomaly = (
        len(evidence) > 0
    )

    # --------------------------------------------------------------
    # DECISION FUSION
    # --------------------------------------------------------------

    suspicious = (
        ai_suspicious
        or investigation_anomaly
    )

    if suspicious:
        status = "SUSPICIOUS"
    else:
        status = "NORMAL"

    return {

        "status":
            status,

        "score":
            score,

        "ai_suspicious":
            ai_suspicious,

        "investigation_anomaly":
            investigation_anomaly,

        "context_evidence":
            context_evidence,

        "timing_evidence":
            timing_evidence,

        "volume_evidence":
            volume_evidence,

        "evidence":
            evidence,

        "context":
            context,
    }


# ======================================================================
# HUMAN-READABLE EXPLANATION
# ======================================================================

def guardian_explain(event, result):
    """
    Convert a Guardian result into a human-readable explanation.

    Returns a string instead of printing directly so that the same
    explanation can later be used by a CLI, API, dashboard, or alert.
    """

    lines = []

    if result["status"] == "SUSPICIOUS":

        lines.append(
            "⚠ SUSPICIOUS COMMUNICATION DETECTED"
        )

    else:

        lines.append(
            "✓ COMMUNICATION BEHAVIOUR NORMAL"
        )

    lines.append("")
    lines.append("EVENT")
    lines.append("-" * 50)

    lines.append(
        f"Source:        {event['source']}"
    )

    lines.append(
        f"Destination:   {event['destination']}"
    )

    lines.append(
        f"Operation:     {event['information']}"
    )

    lines.append(
        f"Protocol:      {event['protocol']}"
    )

    lines.append(
        f"Port:          {event['port']}"
    )

    if "timestamp" in event:

        lines.append(
            f"Timestamp:     {event['timestamp']} seconds"
        )

    if "bytes" in event:

        lines.append(
            f"Message size:  {event['bytes']} bytes"
        )

    lines.append("")
    lines.append("WHAT GUARDIAN OBSERVED")
    lines.append("-" * 50)

    if result["status"] == "SUSPICIOUS":

        lines.append(
            "A communication was observed between "
            f"{event['source']} and {event['destination']}."
        )

        if result["context_evidence"]:

            lines.append(
                "Guardian identified an unusual "
                "communication context."
            )

        if result["timing_evidence"]:

            lines.append(
                "Guardian identified unusual "
                "temporal behaviour."
            )

        if result["volume_evidence"]:

            lines.append(
                "Guardian identified unusual "
                "communication volume."
            )

    else:

        lines.append(
            "The observed communication matches the "
            "behaviour expected by the Guardian baseline."
        )

    lines.append("")
    lines.append("WHY WAS IT FLAGGED?")
    lines.append("-" * 50)

    if result["evidence"]:

        for item in result["evidence"]:
            lines.append(f"• {item}")

    else:

        lines.append(
            "• No contextual, temporal, or volume anomaly detected."
        )

    lines.append("")
    lines.append("ADDITIONAL CHECKS")
    lines.append("-" * 50)

    lines.append(
        "AI anomaly:          "
        + ("YES" if result["ai_suspicious"] else "NO")
    )

    lines.append(
        "Context anomaly:     "
        + ("YES" if result["context_evidence"] else "NO")
    )

    lines.append(
        "Temporal anomaly:    "
        + ("YES" if result["timing_evidence"] else "NO")
    )

    lines.append(
        "Volume anomaly:      "
        + ("YES" if result["volume_evidence"] else "NO")
    )

    lines.append("")
    lines.append("AI ASSESSMENT")
    lines.append("-" * 50)

    lines.append(
        f"Reconstruction error: {result['score']:.6f}"
    )

    lines.append(
        f"Guardian threshold:   {guardian_threshold:.6f}"
    )

    if result["ai_suspicious"]:

        lines.append(
            "The AI model considers this communication "
            "behaviour anomalous."
        )

    else:

        lines.append(
            "The AI model considers this communication "
            "behaviour normal."
        )

    lines.append("")
    lines.append("COMMUNICATION CONTEXT")
    lines.append("-" * 50)

    context = result["context"]

    lines.append(
        "Relationship known:           "
        + (
            "YES"
            if context["relationship_known"]
            else "NO"
        )
    )

    lines.append(
        "Direction known:              "
        + (
            "YES"
            if context["direction_known"]
            else "NO"
        )
    )

    lines.append(
        "Information known globally:   "
        + (
            "YES"
            if context["information_known_globally"]
            else "NO"
        )
    )

    lines.append(
        "Information valid for context:"
        + (
            " YES"
            if context["information_known_for_direction"]
            else " NO"
        )
    )

    lines.append(
        "Protocol known globally:      "
        + (
            "YES"
            if context["protocol_known_globally"]
            else "NO"
        )
    )

    lines.append(
        "Protocol valid for context:   "
        + (
            "YES"
            if context["protocol_known_for_direction"]
            else "NO"
        )
    )

    lines.append("")
    lines.append("RECOMMENDED HUMAN ACTION")
    lines.append("-" * 50)

    if result["status"] == "SUSPICIOUS":

        lines.append(
            "Verify whether this communication is expected "
            "for the current industrial process."
        )

        lines.append(
            "If unexpected, investigate the communication "
            "and determine whether the change was authorized."
        )

    else:

        lines.append(
            "No immediate investigation is indicated by "
            "the current Guardian assessment."
        )

    lines.append("")
    lines.append("AUTOMATIC INTERVENTION")
    lines.append("-" * 50)

    lines.append(
        "None. Guardian is operating in monitoring "
        "and notification mode."
    )

    return "\n".join(lines)


# ======================================================================
# SIMPLE PUBLIC API
# ======================================================================

def analyze_event(event):
    """
    Main public Guardian API.

    Returns:
        {
            "result": structured Guardian analysis,
            "explanation": human-readable explanation
        }
    """

    result = guardian_analyze(event)

    explanation = guardian_explain(
        event,
        result,
    )

    return {
        "result": result,
        "explanation": explanation,
    }