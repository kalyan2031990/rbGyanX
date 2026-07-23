"""Cross-path UTCP agreement tests (engine radiobiology.utcp)."""

import math

import pytest

TCP_RESULT = {
    "AnonPatientID": "TEST001",
    "TCP_Poisson": 0.72,
    "TCP_gEUD": 0.68,
    "TCP_ZM": 0.70,
    "TCP_Logistic": 0.65,
    "TCP_mean": 0.6875,
}

NTCP_RESULTS = [
    {
        "AnonPatientID": "TEST001",
        "structure": "SpinalCord",
        "NTCP_LKB_loglogit": 0.03,
        "NTCP_LKB_probit": 0.025,
        "NTCP_RS": 0.02,
    },
    {
        "AnonPatientID": "TEST001",
        "structure": "Parotid_L",
        "NTCP_LKB_loglogit": 0.18,
        "NTCP_LKB_probit": 0.17,
        "NTCP_RS": 0.16,
    },
    {
        "AnonPatientID": "TEST001",
        "structure": "Parotid_R",
        "NTCP_LKB_loglogit": 0.15,
        "NTCP_LKB_probit": 0.14,
        "NTCP_RS": 0.13,
    },
]


def test_engine_utcp_hn():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[1] / "engine"))
    from radiobiology.utcp import compute_utcp

    result = compute_utcp(TCP_RESULT, NTCP_RESULTS, "HN", ntcp_model="LKB_loglogit")
    expected = 0.72 * (1 - 0.03) * (1 - 0.18) * (1 - 0.15)
    assert not math.isnan(result.UTCP)
    assert abs(result.UTCP - expected) < 0.02
    assert result.n_oars_scored >= 3


def test_utcp_multi_patient_grouping():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[1] / "engine"))
    from radiobiology.utcp import attach_utcp_to_tcp_results

    tcp = [
        {"AnonPatientID": "P1", "TCP_Poisson": 0.7},
        {"AnonPatientID": "P2", "TCP_Poisson": 0.6},
    ]
    ntcp = [
        {"AnonPatientID": "P1", "structure": "SpinalCord", "NTCP_LKB_loglogit": 0.05},
        {"AnonPatientID": "P1", "structure": "Parotid_L", "NTCP_LKB_loglogit": 0.20},
        {"AnonPatientID": "P2", "structure": "SpinalCord", "NTCP_LKB_loglogit": 0.10},
        {"AnonPatientID": "P2", "structure": "Parotid_L", "NTCP_LKB_loglogit": 0.30},
    ]
    attach_utcp_to_tcp_results(tcp, ntcp, "HN")
    utcp_p1 = tcp[0].get("UTCP", math.nan)
    utcp_p2 = tcp[1].get("UTCP", math.nan)
    assert not math.isnan(utcp_p1) and not math.isnan(utcp_p2)
    assert utcp_p2 < utcp_p1
