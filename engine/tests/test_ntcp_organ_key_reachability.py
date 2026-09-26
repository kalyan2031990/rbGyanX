"""Every organ key in the shipped NTCP parameter file must be reachable.

Regression coverage for a class of defect where a YAML organ key doesn't string-match what
canon_target() produces for that organ, so get_oar_structures() silently drops the ROI (a bare
`continue`, no warning, no reason code) before DVH extraction -- the organ's NTCP never computes
for any patient, indistinguishable from that patient simply never having had the structure.

Found by this check: HN/BRAIN_GBM/BRAIN_METS "Brainstem" (canon_target gives "BrainStem"),
BREAST "Lung_Ipsi"/"Lung_Contra" (canon_target collapses both to "LungTotal", which wasn't a
configured key either), PROSTATE "FemoralHead_L"/"_R" (not recognised as an OAR at all --
category UNKNOWN -- because no alias exactly matched the normalised canonical name). All three
fixed in site_params_ntcp_default.yaml / config/structure_aliases.py.
"""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.site_ntcp_params import _DEFAULT, _load_yaml, _validate_default_organ_keys_reachable
from dicom_io.structure_mapper import canon_target


def _all_organ_keys():
    data = _load_yaml(_DEFAULT)
    for site, block in data.items():
        for organ_key in (block.get("organs") or {}):
            yield site, organ_key


@pytest.mark.parametrize("site,organ_key", list(_all_organ_keys()))
def test_organ_key_reachable(site, organ_key):
    """Every shipped organ key must resolve through canon_target() to itself as an OAR."""
    mapped = canon_target(organ_key)
    assert mapped["canonical"] == organ_key, (
        f"{site}/{organ_key}: canon_target() produces {mapped['canonical']!r}, not the key "
        f"itself -- this organ's NTCP will silently never compute for any patient"
    )
    assert mapped["category"] == "OAR", (
        f"{site}/{organ_key}: canon_target() category is {mapped['category']!r}, not 'OAR'"
    )


def test_default_yaml_passes_the_module_load_validation():
    """The shipped file must pass the same check config.site_ntcp_params runs at import time."""
    _validate_default_organ_keys_reachable()  # raises RuntimeError on any unreachable key


def test_validation_actually_fires_on_a_broken_key(tmp_path, monkeypatch):
    """Prove the guard is live: a deliberately-broken fixture must raise, not pass silently."""
    import config.site_ntcp_params as mod

    broken = tmp_path / "broken_ntcp.yaml"
    broken.write_text(yaml.dump({"HN": {"organs": {"Brainstem": {"geud_a": 1.0}}}}))
    monkeypatch.setattr(mod, "_DEFAULT", broken)
    with pytest.raises(RuntimeError, match="do not resolve through canon_target"):
        mod._validate_default_organ_keys_reachable()


# --- pinned regressions for the three specific fixes, so a future rename trips immediately ---

def test_brainstem_key_is_camelcase_in_every_brain_site():
    data = _load_yaml(_DEFAULT)
    for site in ("HN", "BRAIN_GBM", "BRAIN_METS"):
        organs = data[site]["organs"]
        assert "BrainStem" in organs, f"{site}: expected canonical key 'BrainStem'"
        assert "Brainstem" not in organs, f"{site}: stale mis-cased 'Brainstem' key still present"


def test_breast_lung_key_is_the_reachable_canonical():
    data = _load_yaml(_DEFAULT)
    organs = data["BREAST"]["organs"]
    assert "LungTotal" in organs
    assert "Lung_Ipsi" not in organs and "Lung_Contra" not in organs


def test_femoral_head_aliases_self_match():
    from config.structure_aliases import STRUCTURE_ALIASES
    from dicom_io.structure_mapper import normalise_name

    for canonical in ("FemoralHead_L", "FemoralHead_R"):
        assert normalise_name(canonical) in STRUCTURE_ALIASES[canonical], (
            f"{canonical}: its own normalised form must be a self-matching alias"
        )
