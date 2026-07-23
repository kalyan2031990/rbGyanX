# ml_models/model_manager.py

from __future__ import annotations

import json
import pathlib
from dataclasses import asdict
from typing import Any

import joblib
import numpy as np


def save_model(
    model: Any,
    feature_names: list[str],
    model_type: str,
    output_dir: str | pathlib.Path,
    metadata: dict | None = None,
) -> pathlib.Path:
    """
    Save a fitted sklearn pipeline + metadata to disk.
    """
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    pipe_path = out / f"{model_type}_pipeline.joblib"
    meta_path = out / f"{model_type}_metadata.json"

    joblib.dump(model, pipe_path)

    meta = {
        "model_type": model_type,
        "feature_names": feature_names,
        **(metadata or {}),
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    return pipe_path


def load_model(
    model_dir: str | pathlib.Path,
    model_type: str,
) -> tuple[Any, dict]:
    """
    Load a frozen pipeline from disk.
    """
    out = pathlib.Path(model_dir)
    pipe = joblib.load(out / f"{model_type}_pipeline.joblib")
    meta = json.loads((out / f"{model_type}_metadata.json").read_text())
    return pipe, meta


def predict_new_patient(
    model: Any,
    X_new: np.ndarray,
    feature_names: list[str],
    expected_features: list[str],
) -> np.ndarray:
    """
    Apply frozen model to new patient feature vector.
    """
    if list(feature_names) != list(expected_features):
        raise ValueError(
            f"Feature mismatch.\nExpected: {expected_features}\nGot: {feature_names}"
        )
    return model.predict_proba(np.asarray(X_new, dtype=float))[:, 1]
