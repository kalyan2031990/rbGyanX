"""rbGyanX Desktop product version."""

from rbgyanx.paths import APP_NAME, APP_VERSION

__all__ = ["APP_NAME", "APP_VERSION", "product_title"]


def product_title(mode_label: str | None = None) -> str:
    base = f"{APP_NAME} {APP_VERSION}"
    if mode_label:
        return f"{base} — {mode_label}"
    return base
