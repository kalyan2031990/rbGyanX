import math

import pytest


def _make_tcp(pid="PT001", tcp_poisson=0.85):
    return {"AnonPatientID": pid, "TCP_Poisson": tcp_poisson}


def _make_ntcp(oar, ntcp_val, pid="PT001"):
    return {
        "structure": oar,
        "AnonPatientID": pid,
        "NTCP_LKB_loglogit": ntcp_val,
    }


def test_utcp_uses_all_scored_oars_not_just_serial():
    from radiobiology.utcp import compute_utcp

    tcp_r = _make_tcp(tcp_poisson=0.85)
    ntcp_r = [_make_ntcp("Parotid_L", 0.60)]
    result = compute_utcp(tcp_r, ntcp_r, "HN")
    assert result.UTCP < 0.85


def test_utcp_standard_product_formula():
    from radiobiology.utcp import compute_utcp

    tcp_val = 0.80
    ntcp_cord = 0.05
    ntcp_parl = 0.35
    ntcp_parr = 0.30
    tcp_r = _make_tcp(tcp_poisson=tcp_val)
    ntcp_r = [
        _make_ntcp("SpinalCord", ntcp_cord),
        _make_ntcp("Parotid_L", ntcp_parl),
        _make_ntcp("Parotid_R", ntcp_parr),
    ]
    result = compute_utcp(tcp_r, ntcp_r, "HN")
    expected = tcp_val * (1 - ntcp_cord) * (1 - ntcp_parl) * (1 - ntcp_parr)
    assert abs(result.UTCP - expected) < 1e-9


def test_utcp_equals_tcp_when_all_ntcp_zero():
    from radiobiology.utcp import compute_utcp

    tcp_r = _make_tcp(tcp_poisson=0.85)
    ntcp_r = [_make_ntcp("SpinalCord", 0.0), _make_ntcp("Brainstem", 0.0)]
    result = compute_utcp(tcp_r, ntcp_r, "HN")
    assert abs(result.UTCP - 0.85) < 1e-9


def test_utcp_weighted_less_than_standard_when_w_less_1():
    from radiobiology.utcp import compute_utcp

    tcp_r = _make_tcp(tcp_poisson=0.80)
    ntcp_r = [_make_ntcp("Parotid_L", 0.50)]
    result = compute_utcp(tcp_r, ntcp_r, "HN")
    assert result.UTCP_weighted > result.UTCP


def test_utcp_warns_on_missing_critical_oar():
    from radiobiology.utcp import compute_utcp

    tcp_r = _make_tcp(tcp_poisson=0.85)
    result = compute_utcp(tcp_r, [], "HN")
    assert len(result.warnings) > 0
    assert result.n_oars_missing > 0


def test_utcp_lung_sbrt_includes_chest_wall():
    from radiobiology.utcp import UTCP_OAR_MAP

    lung_oars = [e["oar"] for e in UTCP_OAR_MAP.get("LUNG_SBRT", [])]
    assert "LungTotal" in lung_oars
    assert "ChestWall" in lung_oars


def test_utcp_hn_includes_parotid():
    from radiobiology.utcp import UTCP_OAR_MAP

    hn_oars = [e["oar"] for e in UTCP_OAR_MAP.get("HN", [])]
    assert "Parotid_L" in hn_oars
    assert "Parotid_R" in hn_oars


def test_utcp_brain_mets_includes_hippocampus_and_cochlea():
    from radiobiology.utcp import UTCP_OAR_MAP

    mets_oars = [e["oar"] for e in UTCP_OAR_MAP.get("BRAIN_METS", [])]
    assert "Hippocampus_L" in mets_oars
    assert "Cochlea_L" in mets_oars


def test_utcp_brain_gbm_includes_hippocampus():
    from radiobiology.utcp import UTCP_OAR_MAP

    gbm_oars = [e["oar"] for e in UTCP_OAR_MAP.get("BRAIN_GBM", [])]
    assert "Hippocampus_L" in gbm_oars
    assert "Hippocampus_R" in gbm_oars


def test_utcp_brain_gbm_includes_cochlea_and_pituitary():
    from radiobiology.utcp import UTCP_OAR_MAP

    gbm_oars = [e["oar"] for e in UTCP_OAR_MAP.get("BRAIN_GBM", [])]
    assert "Cochlea_L" in gbm_oars
    assert "Pituitary" in gbm_oars


def test_utcp_breast_includes_esophagus_thyroid_brachial():
    from radiobiology.utcp import UTCP_OAR_MAP

    breast_oars = [e["oar"] for e in UTCP_OAR_MAP.get("BREAST", [])]
    assert "Esophagus" in breast_oars
    assert "Thyroid" in breast_oars
    assert "BrachialPlexus" in breast_oars


def test_utcp_breast_spinal_cord_weight_not_1():
    from radiobiology.utcp import UTCP_OAR_MAP

    breast_entries = {
        e["oar"]: e["severity_weight"] for e in UTCP_OAR_MAP.get("BREAST", [])
    }
    if "SpinalCord" in breast_entries:
        assert breast_entries["SpinalCord"] < 1.0


def test_normalize_lung_to_lung_conv_by_default():
    from radiobiology.utcp import normalize_utcp_site

    assert normalize_utcp_site("LUNG") == "LUNG_CONV"
    assert normalize_utcp_site("LUNG_SBRT") == "LUNG_SBRT"
