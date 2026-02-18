import os
import sys

import pytest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.calculations.spectrum import SpectrumCalculator


def test_negative_period_values_are_clipped():
    calc = SpectrumCalculator()
    with pytest.warns(RuntimeWarning):
        T_np, zero_mask, T_safe = calc._sanitize_period_array([-0.1, 0.0, 1.0])
    assert T_np[0] == 0.0
    assert bool(zero_mask[0]) is True
    assert T_safe[0] > 0.0


def _first_region(arr: np.ndarray, TA: float) -> np.ndarray:
    """Helper removing critical points inside 0-TA region."""
    T_AD = TA / 3.0
    mask = (arr < TA) & ~np.isclose(arr, T_AD)
    return arr[mask]


def test_generate_period_array_geomspace_option():
    calc = SpectrumCalculator()
    SDS, SD1, TL = 2.0, 0.4, 6.0
    TA = 0.2 * SD1 / SDS
    T_geom = calc.generate_period_array_optimized(SDS, SD1, TL, use_geomspace=True)
    region = _first_region(T_geom, TA)
    log_steps = np.diff(np.log(region))
    assert np.allclose(log_steps, log_steps[0], rtol=1e-3)


def test_calculate_all_spectra_passes_use_geomspace():
    calc = SpectrumCalculator()
    SDS, SD1, TL = 2.0, 0.4, 6.0
    TA = 0.2 * SD1 / SDS
    result = calc.calculate_all_spectra(SDS, SD1, TL, use_geomspace=True)
    periods = result['period_array'][1:]  # remove T=0
    region = _first_region(periods, TA)
    log_steps = np.diff(np.log(region))
    assert np.allclose(log_steps, log_steps[0], rtol=1e-3)
