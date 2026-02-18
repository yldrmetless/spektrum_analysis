import os
import sys
from dataclasses import asdict

import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from src.calculations.earthquake_stats import (
    EarthquakeStats,
    AllStats,
    PeakStats,
)


def test_calculate_all_stats_returns_dataclasses():
    time = np.linspace(0, 0.4, 5)
    accel = np.array([0.0, 0.1, -0.2, 0.05, 0.0])
    velocity = accel * 0.1
    displacement = velocity * 0.1

    stats = EarthquakeStats.calculate_all_stats(
        time,
        accel,
        velocity,
        displacement,
        dt=0.1,
    )

    assert isinstance(stats, AllStats)
    assert isinstance(stats.pga, PeakStats)
    stats_dict = asdict(stats)
    assert 'pga' in stats_dict and 'rms' in stats_dict
