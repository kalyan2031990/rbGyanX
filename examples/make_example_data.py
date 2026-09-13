"""
Generate the tiny **synthetic** example dataset shipped under ``examples/data/``.

ILLUSTRATIVE ONLY — this data is fabricated from a simple generative model to
demonstrate the software's input formats and workflows. It is **not** patient data
and **not** a validation cohort; never cite example outputs as results.

Run to (re)create the files:

    python examples/make_example_data.py

Produces:
  examples/data/dvh_txt/<PID>_<Structure>_dvh.txt   Eclipse-style DVH text exports
  examples/data/clinical_cohort.csv                 generic clinical-CSV (patient_id,
                                                     endpoint[0/1], covariates)
"""

from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# (patient_id, prescription cGy, PTV coverage factor, parotid mean cGy, cord max cGy)
_PATIENTS = [
    ("EX-001", 7000, 1.00, 2400, 4200),  # good plan
    ("EX-002", 7000, 0.96, 3100, 4600),  # hotter parotids / cord
    ("EX-003", 6600, 0.99, 2600, 4000),
    ("EX-004", 7000, 0.93, 3500, 4800),  # worst OAR sparing
]


def _dvh_block(header: dict[str, str | float], rows: list[tuple[float, float]]) -> str:
    lines = [f"{k}: {v}" for k, v in header.items()]
    lines.append("")
    lines.append("Dose [cGy]  Structure Volume [cm3]")
    lines += [f"{d:.0f}  {v:.1f}" for d, v in rows]
    return "\n".join(lines) + "\n"


def _write_ptv(out: Path, pid: str, rx_cgy: float, cover: float) -> None:
    peak = rx_cgy * 1.03
    rows = [
        (peak, 100.0),
        (rx_cgy, 99.0 * cover),
        (rx_cgy * 0.95, 90.0 * cover),
        (rx_cgy * 0.90, 60.0 * cover),
        (rx_cgy * 0.80, 10.0),
        (rx_cgy * 0.60, 1.0),
    ]
    header = {
        "Patient ID          ": pid,
        "Prescribed dose [cGy]": f"{rx_cgy:.0f}",
        "Mean Dose [cGy]": f"{rx_cgy * 1.01:.0f}",
        "Structure": "PTV70",
        "Number of fractions": "35",
        "Dose per fraction [cGy]": "200",
    }
    (out / f"{pid}_PTV70_dvh.txt").write_text(_dvh_block(header, rows), encoding="utf-8")


def _write_oar(out: Path, pid: str, name: str, mean_cgy: float, max_cgy: float) -> None:
    rows = [
        (0.0, 30.0),
        (mean_cgy * 0.4, 24.0),
        (mean_cgy, 12.0),
        (mean_cgy * 1.4, 5.0),
        (max_cgy, 0.5),
    ]
    header = {
        "Patient ID          ": pid,
        "Mean Dose [cGy]": f"{mean_cgy:.0f}",
        "Structure": name,
        "Number of fractions": "35",
        "Dose per fraction [cGy]": "200",
    }
    (out / f"{pid}_{name}_dvh.txt").write_text(_dvh_block(header, rows), encoding="utf-8")


def _write_clinical(path: Path) -> None:
    # Synthetic xerostomia outcome loosely tracking parotid dose (illustrative only).
    rows = [
        ("EX-001", 0, 61, "M", "no"),
        ("EX-002", 1, 68, "F", "yes"),
        ("EX-003", 0, 57, "M", "no"),
        ("EX-004", 1, 72, "F", "yes"),
        ("EX-005", 0, 64, "M", "no"),
        ("EX-006", 1, 70, "M", "yes"),
        ("EX-007", 0, 59, "F", "no"),
        ("EX-008", 0, 66, "M", "no"),
        ("EX-009", 1, 74, "F", "yes"),
        ("EX-010", 0, 62, "M", "no"),
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["patient_id", "xerostomia_grade2", "age", "sex", "smoker"])
        w.writerows(rows)


def main() -> None:
    dvh_dir = DATA / "dvh_txt"
    dvh_dir.mkdir(parents=True, exist_ok=True)
    for pid, rx, cover, parotid, cord in _PATIENTS:
        _write_ptv(dvh_dir, pid, rx, cover)
        _write_oar(dvh_dir, pid, "Parotid_L", parotid, parotid + 800)
        _write_oar(dvh_dir, pid, "Parotid_R", parotid - 200, parotid + 600)
        _write_oar(dvh_dir, pid, "SpinalCord", cord * 0.4, cord)
    _write_clinical(DATA / "clinical_cohort.csv")
    n_files = len(list(dvh_dir.glob("*.txt")))
    print(f"Wrote {n_files} synthetic DVH files to {dvh_dir}")
    print(f"Wrote synthetic clinical cohort to {DATA / 'clinical_cohort.csv'}")


if __name__ == "__main__":
    main()
