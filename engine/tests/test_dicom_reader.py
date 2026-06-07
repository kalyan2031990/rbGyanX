"""Tests for DICOM plan reader and metadata extraction."""

from types import SimpleNamespace

from dicom_io.dicom_reader import DicomPlanReader, _is_setup_beam, _treatment_beams


def _make_beam(name: str, mu: float, beam_type: str = "STATIC", delivery: str = "TREATMENT"):
    return SimpleNamespace(
        BeamName=name,
        BeamType=beam_type,
        TreatmentDeliveryType=delivery,
        BeamMeterset=mu,
        ControlPointSequence=[],
        RadiationType="PHOTON",
    )


def test_cbct_beam_excluded():
    plan = SimpleNamespace(
        BeamSequence=[
            _make_beam("CBCT_0", 50.0),
            _make_beam("Field_1", 100.0),
            _make_beam("Field_2", 200.0),
        ],
        FractionGroupSequence=[SimpleNamespace(NumberOfFractionsPlanned=30)],
        DoseReferenceSequence=[
            SimpleNamespace(
                DoseReferenceType="TARGET",
                TargetPrescriptionDose=60.0,
            )
        ],
        RTPlanLabel="TEST",
    )
    reader = DicomPlanReader()
    meta = reader.extract_plan_metadata(plan)
    assert meta["n_beams"] == 2
    assert meta["total_mu"] == 300.0
    assert _is_setup_beam(_make_beam("CBCT_0", 50.0))
    assert len(_treatment_beams(plan)) == 2


def test_lq_caution_flag():
    plan = SimpleNamespace(
        BeamSequence=[_make_beam("SBRT_Beam", 500.0)],
        FractionGroupSequence=[SimpleNamespace(NumberOfFractionsPlanned=5)],
        DoseReferenceSequence=[
            SimpleNamespace(
                DoseReferenceType="TARGET",
                TargetPrescriptionDose=60.0,
            )
        ],
        RTPlanLabel="SBRT",
    )
    reader = DicomPlanReader()
    meta = reader.extract_plan_metadata(plan)
    assert meta["dose_per_fraction_gy"] == 12.0
    assert meta["lq_model_caution"] is True


def test_lq_no_caution():
    plan = SimpleNamespace(
        BeamSequence=[_make_beam("IMRT_1", 300.0, beam_type="DYNAMIC")],
        FractionGroupSequence=[SimpleNamespace(NumberOfFractionsPlanned=30)],
        DoseReferenceSequence=[
            SimpleNamespace(
                DoseReferenceType="TARGET",
                TargetPrescriptionDose=60.0,
            )
        ],
        RTPlanLabel="CONV",
    )
    reader = DicomPlanReader()
    meta = reader.extract_plan_metadata(plan)
    assert meta["dose_per_fraction_gy"] == 2.0
    assert meta["lq_model_caution"] is False
