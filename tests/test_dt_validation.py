import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.calculations.earthquake_stats import EarthquakeStats


def test_calculate_pga_invalid_dt():
    data = np.array([0.1, -0.2])
    with pytest.raises(ValueError):
        EarthquakeStats.calculate_pga(data, dt=0)


def test_calculate_pgv_invalid_dt():
    data = np.array([0.1, -0.2])
    with pytest.raises(ValueError):
        EarthquakeStats.calculate_pgv(data, dt=-0.01)


def test_calculate_pgd_invalid_dt():
    data = np.array([0.1, -0.2])
    with pytest.raises(ValueError):
        EarthquakeStats.calculate_pgd(data, dt=0)


def test_calculate_cav_invalid_dt():
    data = np.array([0.1, -0.2])
    with pytest.raises(ValueError):
        EarthquakeStats.calculate_cav(data, dt=0)
