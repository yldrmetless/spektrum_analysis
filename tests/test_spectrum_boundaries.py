import numpy as np
from src.calculations.spectrum import SpectrumCalculator


def test_horizontal_continuity_at_TA_TB_TL():
    c = SpectrumCalculator()
    SDS, SD1, TL = 1.10, 0.39, 6.0
    eps = 1e-9
    TA = 0.2 * SD1 / SDS
    TB = SD1 / SDS
    Ts = np.array([TA - eps, TA + eps, TB - eps, TB + eps, TL - eps, TL + eps])
    Sa, *_ = c.calculate_horizontal_spectrum(Ts, SDS=SDS, SD1=SD1, TL=TL)
    assert abs(Sa[0] - Sa[1]) < 1e-6
    assert abs(Sa[2] - Sa[3]) < 1e-6
    assert abs(Sa[4] - Sa[5]) < 1e-6


def test_vertical_defined_up_to_TLD():
    c = SpectrumCalculator()
    SDS, SD1, TL = 1.10, 0.39, 6.0
    T = np.linspace(0, 2 * TL, 400)
    SaD, TAD, TBD = c.calculate_vertical_spectrum(T, SDS=SDS, SD1=SD1, TL=TL)
    # T<=TL/2 için tüm değerler sonlu
    assert np.isfinite(SaD[T <= TL / 2.0]).all()
    # T>TL/2 için çizimde kullanılmaması adına NaN üretimi kabul edilir
    assert np.isnan(SaD[T > TL / 2.0]).all()


