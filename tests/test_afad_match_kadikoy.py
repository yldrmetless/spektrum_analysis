import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data.loader import DataLoader
from src.data.processor import DataProcessor
from src.calculations.coefficients import CoefficientCalculator


KADIKOY_LAT = 41.008073
KADIKOY_LON = 29.040003
DD_LEVEL = "DD-2"

EXPECTED_PGA = 0.3742423165
EXPECTED_SS = 0.9100368480
EXPECTED_S1 = 0.2524271918
EXPECTED_PGV = 23.3420253822
EXPECTED_SDS = 1.0920442177
EXPECTED_SD1 = 0.3786407878


def _load_loader_with_data():
    data_loader = DataLoader()
    param_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "parametre.xlsx"))
    df = data_loader.load_file(param_path)
    assert df is not None and len(df) > 0
    return data_loader


def test_afad_match_kadikoy_point():
    loader = _load_loader_with_data()

    interpolated = loader.get_interpolated_values(
        KADIKOY_LAT,
        KADIKOY_LON,
        DD_LEVEL,
        cols=["PGA", "Ss", "S1", "PGV"],
        k=8,
        power=2.0,
    )

    assert interpolated["PGA"] == pytest.approx(EXPECTED_PGA, abs=0.001)
    assert interpolated["Ss"] == pytest.approx(EXPECTED_SS, abs=0.001)
    assert interpolated["S1"] == pytest.approx(EXPECTED_S1, abs=0.001)
    assert interpolated["PGV"] == pytest.approx(EXPECTED_PGV, abs=0.001)

    processor = DataProcessor()
    processor.data_loader = loader
    ss_val, s1_val = processor.get_parameters_for_location(KADIKOY_LAT, KADIKOY_LON, DD_LEVEL)

    assert ss_val == pytest.approx(EXPECTED_SS, abs=0.001)
    assert s1_val == pytest.approx(EXPECTED_S1, abs=0.001)

    coeff_calc = CoefficientCalculator()
    fs, f1 = coeff_calc.calculate_site_coefficients(ss_val, s1_val, "ZC")
    sds, sd1 = coeff_calc.calculate_design_parameters(ss_val, s1_val, fs, f1)

    assert sds == pytest.approx(EXPECTED_SDS, abs=0.001)
    assert sd1 == pytest.approx(EXPECTED_SD1, abs=0.001)
