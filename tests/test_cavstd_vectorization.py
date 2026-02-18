import os
import sys
import numpy as np
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from src.calculations.earthquake_stats import EarthquakeStats


def _cavstd_loop(accel, dt, unit='g', threshold=0.025):
    accel = np.asarray(accel, dtype=float)
    accel_g = EarthquakeStats._convert_acceleration_to_g(accel, unit)
    accel_g_clean = np.where(np.isfinite(accel_g), accel_g, 0.0)
    accel_clean = np.where(np.isfinite(accel), accel, 0.0)

    window_size = max(1, int(1.0 / dt))
    cavstd = 0.0
    for start in range(0, len(accel), window_size):
        end = min(start + window_size, len(accel))
        window_g = accel_g_clean[start:end]
        if np.max(np.abs(window_g)) >= threshold:
            cavstd += np.trapezoid(np.abs(accel_clean[start:end]), dx=dt)
    return cavstd


def test_cavstd_vectorized_matches_loop():
    accel = np.array([0.01, 0.04, -0.03, 0.005, 0.002,
                      0.015, 0.012, 0.020, 0.018])
    dt = 0.2
    threshold = 0.025

    expected = _cavstd_loop(accel, dt, threshold=threshold)
    result = EarthquakeStats.calculate_cav(
        accel, dt, unit='g', standardize=True, threshold_g=threshold
    )

    assert result.value == pytest.approx(expected)
    expected_si = EarthquakeStats._convert_cav_to_si(expected, 'g')
    assert result.value_si == pytest.approx(expected_si)

