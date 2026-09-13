"""
BASIC example — clinic workflow on synthetic DVH-text exports (no patient data, no ML).

Runs the rbGyanX engine over the shipped synthetic Eclipse-style DVH text folder and
writes a TCP/NTCP report. This mirrors the command a clinic user would type:

    python -m rbgyanx_engine --dvh-dir examples/data/dvh_txt \
        --endpoint both --mode basic --site HN --no-ml --output-dir examples/output/basic

ILLUSTRATIVE ONLY: the inputs are fabricated (see examples/make_example_data.py). The
numbers demonstrate the software end-to-end; they are not clinical or validation results.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DVH_DIR = HERE / "data" / "dvh_txt"
OUT_DIR = HERE / "output" / "basic"


def main() -> int:
    if not any(DVH_DIR.glob("*.txt")):
        print("Example data missing — generating it first...")
        subprocess.run([sys.executable, str(HERE / "make_example_data.py")], check=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "rbgyanx_engine",
        "--dvh-dir",
        str(DVH_DIR),
        "--endpoint",
        "both",
        "--mode",
        "basic",
        "--site",
        "HN",
        "--no-ml",
        "--output-dir",
        str(OUT_DIR),
    ]
    print("Running:", " ".join(cmd), "\n")
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        print(f"\nOutputs written to: {OUT_DIR}")
        print("  tcp_benchmarking.xlsx   TCP per structure/model")
        print("  site_detection.csv      auto-detected site per DVH")
        print("  qa_report.json          input-quality checks")
        print("  provenance.json         run metadata (versions, config)")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
