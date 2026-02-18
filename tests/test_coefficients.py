import os
import sys

import pytest
import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from src.calculations.coefficients import CoefficientCalculator
from config.constants import FS_VALUES, F1_VALUES


def test_calculate_site_coefficients_valid_input():
    calc = CoefficientCalculator()
    ss, s1, soil = 0.75, 0.30, "ZC"
    fs_exp = np.interp(ss, [0.25, 0.50, 0.75, 1.00, 1.25, 1.50], FS_VALUES[soil])
    f1_exp = np.interp(s1, [0.10, 0.20, 0.30, 0.40, 0.50, 0.60], F1_VALUES[soil])
    fs, f1 = calc.calculate_site_coefficients(ss, s1, soil)
    assert fs == pytest.approx(fs_exp)
    assert f1 == pytest.approx(f1_exp)


def test_calculate_site_coefficients_ss_out_of_range():
    calc = CoefficientCalculator()
    with pytest.raises(ValueError):
        calc.calculate_site_coefficients(0.10, 0.30, "ZC")


def test_calculate_site_coefficients_s1_out_of_range():
    calc = CoefficientCalculator()
    with pytest.raises(ValueError):
        calc.calculate_site_coefficients(0.75, 0.90, "ZC")
