"""PyInstaller runtime hook: set app root before rbGyanX imports."""
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    os.environ.setdefault("RBGYANX_APP_ROOT", str(Path(sys.executable).resolve().parent))
