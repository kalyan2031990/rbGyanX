"""Tests for structure name canonicalisation."""

from dicom_io.structure_mapper import canon_target


def test_canonical_names():
    assert canon_target("GTVp")["canonical"] == "GTV"
    assert canon_target("gtvn")["canonical"] == "GTV"
    assert canon_target("PTV 60Gy/30FR")["canonical"] == "PTV"
    assert canon_target("CouchSurface")["canonical"] == "COUCH"
    assert canon_target("Lumpectomy_Cavity")["canonical"] == "BOOST"
    assert canon_target("parotid_L")["canonical"] == "Parotid_L"
    assert canon_target("LungTOTAL")["canonical"] == "LungTotal"
    assert canon_target("igtv")["canonical"] == "ITV"
    assert canon_target("UNKNOWN_STRUCT_XYZ")["confidence"] == "LOW"


def test_roi_type_tag_priority():
    result = canon_target("AnyRandomName123", roi_interpreted_type="GTV")
    assert result["canonical"] == "GTV"
    assert result["confidence"] == "HIGH"
