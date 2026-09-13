"""
Site parameter routing: resolve correctly, or raise. Never substitute.

Three concrete defects prompted this file, but the point is to pin the *class* of bug rather
than the three instances, because all three were variations of one thing -- three registries
(``_SITE_KEY_MAP``, ``SITE_PARAMS``, ``site_params_default.yaml``) that had drifted out of
agreement with each other, with no test comparing them.

The instances:

* ``PROSTATE_SBRT`` had parameters in the YAML that differ materially from conventional prostate
  (TCD50 36.25 Gy vs 72.0), but was absent from ``_SITE_KEY_MAP`` and so was rejected as an
  unknown site. The parameters existed and could not be reached.
* ``PELVIS`` was in ``_SITE_KEY_MAP`` with no parameter object anywhere, so it failed with
  "Site 'PELVIS' not found in SITE_PARAMS" -- an internal detail, not an answer. Worse, the
  detector maps PELVIS, CERVIX and ENDOMETRIUM onto that key, so it was reachable from real data.
* ``LUNG_SBRT`` was mapped to ``LUNG``, so an SBRT request was answered with
  conventional-fractionation parameters and nothing said so.

The invariant below (every mapped key either loads as itself or raises) is what makes all three
impossible to reintroduce.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from config.site_params import (
    _SITE_KEY_MAP,
    _SITES_WITHOUT_TCP_PARAMS,
    SITE_PARAMS,
    SiteParamsUnavailable,
    load_site_params,
)

pytestmark = pytest.mark.unit

_YAML = Path(__file__).resolve().parents[1] / "config" / "site_params_default.yaml"


def _yaml_keys() -> set[str]:
    data = yaml.safe_load(_YAML.read_text(encoding="utf-8"))
    return {k for k, v in data.items() if isinstance(v, dict)}


# ------------------------------------------------------------- the invariant


@pytest.mark.parametrize("requested", sorted(_SITE_KEY_MAP))
def test_every_mapped_site_either_loads_or_raises_clearly(requested: str) -> None:
    """No mapped key may fail with an internal error, and none may return a foreign site."""
    try:
        params = load_site_params(requested)
    except SiteParamsUnavailable as exc:
        # Allowed, but only when declared, and the reason must actually be stated.
        assert _SITE_KEY_MAP[requested] in _SITES_WITHOUT_TCP_PARAMS
        assert len(str(exc)) > 60, "an unavailable site must explain itself"
        return

    expected = _SITE_KEY_MAP[requested]
    assert params.site == expected, (
        f"requesting {requested!r} returned parameters for {params.site!r}: silent substitution"
    )


def test_no_mapped_key_is_missing_a_parameter_object() -> None:
    """The PELVIS defect, stated directly: mapped targets must be parameterised or declared."""
    orphans = {
        key: target
        for key, target in _SITE_KEY_MAP.items()
        if target not in SITE_PARAMS and target not in _SITES_WITHOUT_TCP_PARAMS
    }
    assert orphans == {}, f"mapped sites with no parameters and no declaration: {orphans}"


def test_every_yaml_site_is_reachable() -> None:
    """The PROSTATE_SBRT defect: parameters in the YAML that nothing can load are dead weight."""
    unreachable = sorted(_yaml_keys() - set(SITE_PARAMS))
    assert unreachable == [], (
        f"site_params_default.yaml defines {unreachable} but no parameter object exists, "
        "so those values can never be loaded"
    )


def test_declared_unavailable_sites_are_not_also_parameterised() -> None:
    """A site cannot be both unavailable and available."""
    both = sorted(set(_SITES_WITHOUT_TCP_PARAMS) & set(SITE_PARAMS))
    assert both == [], f"sites declared unavailable but present in SITE_PARAMS: {both}"


# -------------------------------------------------------- the three instances


def test_prostate_sbrt_loads_its_own_parameters() -> None:
    """It must load, and it must not be conventional prostate wearing an SBRT label."""
    sbrt = load_site_params("PROSTATE_SBRT")
    conventional = load_site_params("PROSTATE")

    assert sbrt.site == "PROSTATE_SBRT"
    assert sbrt.TCD50_gy == pytest.approx(36.25)
    assert sbrt.TCD50_gy != conventional.TCD50_gy
    assert sbrt.gamma50 != conventional.gamma50


def test_lung_sbrt_resolves_to_itself_not_to_lung() -> None:
    """The substitution is gone: the returned object names the site that was requested."""
    assert load_site_params("LUNG_SBRT").site == "LUNG_SBRT"
    assert load_site_params("LUNG").site == "LUNG"


def test_lung_sbrt_declares_that_its_values_are_conventional() -> None:
    """Honesty requirement.

    No SBRT-specific lung TCP set has been adopted, so LUNG_SBRT carries the conventional
    numbers. That is acceptable only because the object says so -- if someone later changes the
    values, this test should be updated deliberately, not silently.
    """
    sbrt = load_site_params("LUNG_SBRT")
    notes = sbrt.notes.upper()
    assert "CONVENTIONAL" in notes
    assert sbrt.TCD50_gy == pytest.approx(load_site_params("LUNG").TCD50_gy)


def test_pelvis_raises_with_a_reason_rather_than_an_internal_error() -> None:
    with pytest.raises(SiteParamsUnavailable) as excinfo:
        load_site_params("PELVIS")

    message = str(excinfo.value)
    assert "PELVIS" in message
    assert "not found in SITE_PARAMS" not in message, "internal detail leaked to the caller"
    assert "multi-target" in message or "target site" in message


def test_unknown_site_is_distinguishable_from_unparameterised_site() -> None:
    """Callers need to tell a typo from a legitimate but unsupported request."""
    with pytest.raises(ValueError) as unknown:
        load_site_params("NOT_A_SITE")
    assert not isinstance(unknown.value, SiteParamsUnavailable)

    with pytest.raises(SiteParamsUnavailable):
        load_site_params("PELVIS")


def test_the_supported_list_in_the_error_is_accurate() -> None:
    """The old message was hand-maintained and had gone stale, omitting PROSTATE and LIVER."""
    with pytest.raises(ValueError) as excinfo:
        load_site_params("NOT_A_SITE")

    message = str(excinfo.value)
    for site in ("PROSTATE", "LIVER", "PROSTATE_SBRT", "LUNG_SBRT"):
        assert site in message, f"{site} loads but is not advertised as supported"


# --------------------------------------------------- reachable from real data


@pytest.mark.parametrize("detected", ["PELVIS", "CERVIX", "ENDOMETRIUM"])
def test_detected_pelvic_sites_fail_understandably(detected: str) -> None:
    """These are reachable from DICOM, so their failure has to be a sentence, not a traceback."""
    from dicom_io.site_detector import params_site_key

    with pytest.raises(SiteParamsUnavailable):
        load_site_params(params_site_key(detected, ""))


@pytest.mark.parametrize(
    ("detected", "expected"),
    [
        ("LUNG_SBRT", "LUNG_SBRT"),
        ("PROSTATE_SBRT", "PROSTATE_SBRT"),
        ("LUNG", "LUNG"),
        ("NSCLC", "LUNG"),
        ("CAP", "PROSTATE"),
    ],
)
def test_detector_keys_round_trip_without_substitution(detected: str, expected: str) -> None:
    """The detector and the parameter loader must agree end to end."""
    from dicom_io.site_detector import params_site_key

    key = params_site_key(detected, "")
    assert key == expected
    assert load_site_params(key).site == expected
