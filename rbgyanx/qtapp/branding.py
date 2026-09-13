"""
rbGyanX branding for the Qt shell (v2 Phase 4 · Slice 3).

Reuses the EXISTING assets — ``assets/icon.png``, ``assets/splash.png``,
``assets/ashoka_chakra.svg`` — so the Qt application is visually the same product as the
Tkinter one. No new logo is introduced.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["asset_dir", "icon_path", "splash_path", "chakra_path", "PALETTE", "STYLESHEET"]


def _base_dir() -> Path:
    """Repo root (or the PyInstaller bundle dir) — mirrors ``_rbgyanx_base_dir`` in the GUI."""
    import sys

    if getattr(sys, "frozen", False):  # PyInstaller onefile/onedir
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def asset_dir() -> Path:
    return _base_dir() / "assets"


def icon_path() -> Path | None:
    p = asset_dir() / "icon.png"
    return p if p.exists() else None


def splash_path() -> Path | None:
    p = asset_dir() / "splash.png"
    return p if p.exists() else None


def chakra_path() -> Path | None:
    p = asset_dir() / "ashoka_chakra.svg"
    return p if p.exists() else None


#: Clinical, low-chrome palette. Readable at a glance in a treatment-planning room.
PALETTE = {
    "bg": "#f5f7fa",
    "surface": "#ffffff",
    "border": "#d6dce5",
    "text": "#1c2530",
    "muted": "#5b6878",
    "primary": "#1f77b4",
    "danger": "#d62728",
    "ok": "#2ca02c",
    "warn": "#ff7f0e",
}

#: Qt stylesheet — deliberately restrained; medical UI should not compete with the data.
STYLESHEET = f"""
QWidget {{
    background: {PALETTE["bg"]};
    color: {PALETTE["text"]};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 10pt;
}}
QGroupBox {{
    background: {PALETTE["surface"]};
    border: 1px solid {PALETTE["border"]};
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {PALETTE["muted"]};
}}
QPushButton {{
    background: {PALETTE["primary"]};
    color: white;
    border: none;
    border-radius: 5px;
    padding: 7px 16px;
    font-weight: 600;
}}
QPushButton:hover  {{ background: #17608f; }}
QPushButton:disabled {{ background: #b9c3cf; color: #eef2f6; }}
QPushButton[variant="secondary"] {{
    background: {PALETTE["surface"]};
    color: {PALETTE["text"]};
    border: 1px solid {PALETTE["border"]};
}}
QLineEdit, QComboBox, QPlainTextEdit {{
    background: {PALETTE["surface"]};
    border: 1px solid {PALETTE["border"]};
    border-radius: 5px;
    padding: 5px 8px;
}}
QPlainTextEdit {{ font-family: "Cascadia Mono", Consolas, monospace; font-size: 9pt; }}
QProgressBar {{
    background: {PALETTE["surface"]};
    border: 1px solid {PALETTE["border"]};
    border-radius: 5px;
    height: 16px;
    text-align: center;
}}
QProgressBar::chunk {{ background: {PALETTE["primary"]}; border-radius: 4px; }}
QTabBar::tab {{
    background: transparent;
    padding: 8px 16px;
    border-bottom: 2px solid transparent;
    color: {PALETTE["muted"]};
}}
QTabBar::tab:selected {{
    color: {PALETTE["primary"]};
    border-bottom: 2px solid {PALETTE["primary"]};
    font-weight: 600;
}}
QTableWidget {{
    background: {PALETTE["surface"]};
    border: 1px solid {PALETTE["border"]};
    gridline-color: {PALETTE["border"]};
}}
QHeaderView::section {{
    background: {PALETTE["bg"]};
    border: none;
    border-bottom: 1px solid {PALETTE["border"]};
    padding: 6px;
    font-weight: 600;
}}
"""
