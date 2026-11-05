"""Pin what the dosiomics module claims and what it actually computes (defects #53, #54).

Defect #53: the module docstring said the 3-D texture dosiomics "are computed by this module",
contradicting its own preceding sentence and describing a capability that does not exist here. The
sentence came from re-aiming a pointer to ``analysis/dosiomics/`` at this module when that
directory was removed.

Defect #54: ``extract_dosiomics_features(use_pyradiomics=True)`` was accepted and silently ignored
-- the caller got first-order features with no indication the request had been dropped.

These tests fail on v1.4.0: there, ``use_pyradiomics=True`` returns a dict instead of raising, and
the docstring contains the false texture claim.
"""

from __future__ import annotations

import numpy as np
import pytest

from rbgyanx_advanced.dose3d import dosiomics
from rbgyanx_advanced.dose3d.dosiomics import extract_dosiomics_features

TEXTURE_NAMES = ("glcm", "glrlm", "glszm", "ngldm", "ngtdm")


@pytest.fixture
def voxels() -> np.ndarray:
    return np.linspace(10.0, 60.0, 500)


def test_use_pyradiomics_true_refuses_instead_of_ignoring(voxels):
    """#54: the request must fail loudly, not be dropped on the floor."""
    with pytest.raises(NotImplementedError) as exc:
        extract_dosiomics_features(voxels, oar_name="Parotid_L", use_pyradiomics=True)
    message = str(exc.value)
    assert "#54" in message, "the refusal must name the defect it closes"
    assert "first-order" in message.lower()


def test_use_pyradiomics_false_is_unchanged(voxels):
    """The default path keeps working: the fix refuses a claim, it does not remove a feature."""
    feats = extract_dosiomics_features(voxels, oar_name="Parotid_L", use_pyradiomics=False)
    assert feats, "the default call must still return features"
    assert feats == extract_dosiomics_features(voxels, oar_name="Parotid_L")


def test_the_dead_pyradiomics_probe_is_gone():
    """#54: the module-level flag that nothing read is removed, not left as decoration."""
    assert not hasattr(dosiomics, "_PYRADIOMICS_AVAILABLE")


def test_no_feature_is_named_after_a_texture_family(voxels):
    """#53: the returned keys are the honest scope -- first-order only, no texture features."""
    feats = extract_dosiomics_features(voxels, oar_name="Parotid_L")
    offenders = [key for key in feats if any(fam in key.lower() for fam in TEXTURE_NAMES)]
    assert not offenders, f"texture-named features returned by a first-order module: {offenders}"


def test_the_module_docstring_does_not_claim_texture_features():
    """#53: the docstring must not say this module computes GLCM/GLRLM/GLSZM.

    Asserted on the text because the defect was a documentation claim, not a code path: there was
    nothing to execute that would reveal it. If a texture implementation is ever added here, this
    test is the one to update -- and the KNOWN_LIMITATIONS entry with it.

    The forbidden pattern is the *claim form*, family list and all, not the bare phrase "computed
    by this module". The corrected docstring quotes the old sentence in order to explain it, and a
    bare-phrase assertion failed on that quotation when this test was first written -- it would
    have forced the correction to be silent about what it was correcting.
    """
    doc = dosiomics.__doc__ or ""
    assert "first-order dose statistics only" in doc
    assert (
        "(GLCM / GLRLM / GLSZM) are computed by this module" not in doc
    ), "the false texture claim is back in the module docstring (defect #53)"
    assert "no texture features" in doc.lower()
