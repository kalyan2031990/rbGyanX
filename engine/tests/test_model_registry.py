import math

import numpy as np
import pandas as pd

from radiobiology.model_registry import clear_registries, register_tcp_model


class _DummyTCP:
    def compute_tcp_dvh(self, dvh_df, n_fractions, site_params, target_type="GTV"):
        return {"tcp": 0.42, "model": "DUMMY"}


def test_register_tcp_model_in_compute_all(uniform_dvh_result):
    clear_registries()
    register_tcp_model("DUMMY", _DummyTCP())
    from radiobiology.tcp_calculator import TCPCalculator
    from config.site_params import load_site_params

    calc = TCPCalculator()
    params = load_site_params("HN")
    row = calc.compute_all(
        uniform_dvh_result,
        {"prescription_dose_gy": 70, "n_fractions": 35, "dose_per_fraction_gy": 2},
        params,
    )
    assert row.get("TCP_DUMMY") == 0.42
    clear_registries()
