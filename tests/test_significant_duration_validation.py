import numpy as np
import pytest

from src.calculations.earthquake_stats import EarthquakeStats


def test_significant_duration_percent_order_validation():
    accel = np.ones(100)
    dt = 0.01
    with pytest.raises(ValueError):
        EarthquakeStats.calculate_significant_duration(accel, dt, start_percent=95, end_percent=5)
    with pytest.raises(ValueError):
        EarthquakeStats.calculate_significant_duration(accel, dt, start_percent=50, end_percent=50)


def test_significant_duration_valid_call():
    accel = np.ones(100)
    dt = 0.01
    result = EarthquakeStats.calculate_significant_duration(accel, dt, start_percent=5, end_percent=95)
    assert result.start_percent == 5
    assert result.end_percent == 95
