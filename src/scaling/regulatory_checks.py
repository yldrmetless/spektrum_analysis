"""
3B Ölçekleme için Yönetmelik Uyumluluk Kontrolü
==============================================

ASCE 7-16 ve TBDY uyumluluk kontrolleri.
Suite ortalaması testleri ve yönetmelik bandı kontrolleri.
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from .scale_3d import ScaleResult3D


@dataclass
class RegulatoryCheckResult:
    """Yönetmelik kontrol sonuçları."""
    passed: bool
    message: str
    details: Dict[str, Any]


@dataclass
class SuiteAverageResult:
    """Suite ortalaması sonuçları."""
    arithmetic_mean: np.ndarray
    geometric_mean: np.ndarray
    target_spectrum: np.ndarray
    T_grid: np.ndarray
    component: str


def calculate_suite_averages(
    results: List[ScaleResult3D],
    component: str = "GM",
    T_grid: Optional[np.ndarray] = None
) -> SuiteAverageResult:
    """
    Suite ortalamalarını hesaplar.
    
    Args:
        results: Ölçekleme sonuçları listesi
        component: "FN", "FP", "V", "GM"
        T_grid: Periyot ızgarası
        
    Returns:
        SuiteAverageResult: Suite ortalaması sonuçları
    """
    if not results:
        raise ValueError("Sonuç listesi boş")
    
    if T_grid is None:
        T_grid = results[0].T_grid
    
    # Bileşen seçimi
    if component == "FN":
        spectra = [r.SA_FN_scaled for r in results]
    elif component == "FP":
        spectra = [r.SA_FP_scaled for r in results]
    elif component == "V":
        spectra = [r.SA_V_scaled for r in results if r.SA_V_scaled is not None]
        if not spectra:
            raise ValueError("Düşey bileşen verisi yok")
    elif component == "GM":
        spectra = [r.SA_GM for r in results]
    else:
        raise ValueError(f"Bilinmeyen bileşen: {component}")
    
    # Ortalamalar
    spectra_array = np.array(spectra)
    
    # Aritmetik ortalama
    arithmetic_mean = np.mean(spectra_array, axis=0)
    
    # Geometrik ortalama
    geometric_mean = np.exp(np.mean(np.log(spectra_array), axis=0))
    
    # Hedef spektrum (ilk kayıttan al)
    target_spectrum = results[0].SA_target if hasattr(results[0], 'SA_target') else None
    
    return SuiteAverageResult(
        arithmetic_mean=arithmetic_mean,
        geometric_mean=geometric_mean,
        target_spectrum=target_spectrum,
        T_grid=T_grid,
        component=component
    )


def check_asce_7_16_compliance(
    suite_average: SuiteAverageResult,
    target_spectrum: np.ndarray,
    T_design: float,
    threshold_ratio: float = 0.9,
    band_range: Tuple[float, float] = (0.2, 2.0)
) -> RegulatoryCheckResult:
    """
    ASCE 7-16 uyumluluk kontrolü yapar.
    
    Suite ortalaması 0.2T-2.0T aralığında hedefin %90'ının altına düşmemelidir.
    
    Args:
        suite_average: Suite ortalaması sonuçları
        target_spectrum: Hedef spektrum
        T_design: Tasarım periyodu
        threshold_ratio: Eşik oranı (varsayılan: 0.9)
        band_range: Bant aralığı (T_design çarpanları)
        
    Returns:
        RegulatoryCheckResult: Kontrol sonucu
    """
    T_grid = suite_average.T_grid
    suite_mean = suite_average.arithmetic_mean
    
    # Bant aralığını hesapla
    T_min = band_range[0] * T_design
    T_max = band_range[1] * T_design
    
    # Bant içindeki noktaları bul
    band_mask = (T_grid >= T_min) & (T_grid <= T_max)
    
    if not np.any(band_mask):
        return RegulatoryCheckResult(
            passed=False,
            message=f"Bant aralığında periyot noktası yok: {T_min:.3f}-{T_max:.3f} s",
            details={"T_min": T_min, "T_max": T_max, "band_mask": band_mask}
        )
    
    # Bant içindeki değerleri al
    T_band = T_grid[band_mask]
    suite_band = suite_mean[band_mask]
    target_band = target_spectrum[band_mask]
    
    # Eşik değerleri hesapla
    threshold_values = threshold_ratio * target_band
    
    # Kontrol
    violations = suite_band < threshold_values
    n_violations = np.sum(violations)
    
    if n_violations == 0:
        message = f"ASCE 7-16 uyumlu: Suite ortalaması {T_min:.3f}-{T_max:.3f} s aralığında hedefin %{threshold_ratio*100:.0f}'ının altına düşmüyor"
        passed = True
    else:
        violation_indices = np.where(violations)[0]
        violation_periods = T_band[violation_indices]
        violation_ratios = suite_band[violation_indices] / target_band[violation_indices]
        
        message = f"ASCE 7-16 uyumsuz: {n_violations} noktada ihlal. En düşük oran: {np.min(violation_ratios):.3f}"
        passed = False
    
    details = {
        "T_design": T_design,
        "T_min": T_min,
        "T_max": T_max,
        "threshold_ratio": threshold_ratio,
        "n_violations": n_violations,
        "violation_periods": violation_periods.tolist() if n_violations > 0 else [],
        "violation_ratios": violation_ratios.tolist() if n_violations > 0 else [],
        "min_ratio": np.min(suite_band / target_band) if len(suite_band) > 0 else 1.0
    }
    
    return RegulatoryCheckResult(passed=passed, message=message, details=details)


def check_tbdy_compliance(
    suite_average: SuiteAverageResult,
    target_spectrum: np.ndarray,
    T_design: float,
    threshold_ratio: float = 0.9,
    band_range: Tuple[float, float] = (0.2, 1.5)
) -> RegulatoryCheckResult:
    """
    TBDY uyumluluk kontrolü yapar.
    
    TBDY için bant aralığı 0.2T-1.5T'dir (ASCE 7-10/7-05 ile aynı).
    
    Args:
        suite_average: Suite ortalaması sonuçları
        target_spectrum: Hedef spektrum
        T_design: Tasarım periyodu
        threshold_ratio: Eşik oranı
        band_range: Bant aralığı (T_design çarpanları)
        
    Returns:
        RegulatoryCheckResult: Kontrol sonucu
    """
    return check_asce_7_16_compliance(
        suite_average, target_spectrum, T_design, threshold_ratio, band_range
    )


def check_spectral_shape_compliance(
    suite_average: SuiteAverageResult,
    target_spectrum: np.ndarray,
    T_design: float,
    shape_tolerance: float = 0.1
) -> RegulatoryCheckResult:
    """
    Spektral şekil uyumluluğunu kontrol eder.
    
    Args:
        suite_average: Suite ortalaması sonuçları
        target_spectrum: Hedef spektrum
        T_design: Tasarım periyodu
        shape_tolerance: Şekil toleransı
        
    Returns:
        RegulatoryCheckResult: Kontrol sonucu
    """
    T_grid = suite_average.T_grid
    suite_mean = suite_average.arithmetic_mean
    
    # Tasarım periyodu civarındaki noktaları bul
    T_design_idx = np.argmin(np.abs(T_grid - T_design))
    T_range = T_grid[max(0, T_design_idx-5):min(len(T_grid), T_design_idx+6)]
    
    # Şekil uyumluluğunu kontrol et
    shape_ratios = suite_mean / target_spectrum
    shape_std = np.std(shape_ratios)
    
    if shape_std <= shape_tolerance:
        message = f"Spektral şekil uyumlu: Standart sapma {shape_std:.3f} ≤ {shape_tolerance}"
        passed = True
    else:
        message = f"Spektral şekil uyumsuz: Standart sapma {shape_std:.3f} > {shape_tolerance}"
        passed = False
    
    details = {
        "T_design": T_design,
        "shape_tolerance": shape_tolerance,
        "shape_std": shape_std,
        "shape_ratios": shape_ratios.tolist(),
        "T_range": T_range.tolist()
    }
    
    return RegulatoryCheckResult(passed=passed, message=message, details=details)


def perform_comprehensive_regulatory_checks(
    results: List[ScaleResult3D],
    target_spectrum: np.ndarray,
    T_design: float,
    component: str = "GM",
    checks: Optional[Dict[str, Any]] = None
) -> Dict[str, RegulatoryCheckResult]:
    """
    Kapsamlı yönetmelik kontrolleri yapar.
    
    Args:
        results: Ölçekleme sonuçları listesi
        target_spectrum: Hedef spektrum
        T_design: Tasarım periyodu
        component: Bileşen
        checks: Kontrol parametreleri
        
    Returns:
        Dict[str, RegulatoryCheckResult]: Kontrol sonuçları
    """
    if checks is None:
        checks = {
            "asce_7_16": {"threshold_ratio": 0.9, "band_range": (0.2, 2.0)},
            "tbdy": {"threshold_ratio": 0.9, "band_range": (0.2, 1.5)},
            "spectral_shape": {"shape_tolerance": 0.1}
        }
    
    # Suite ortalaması hesapla
    suite_average = calculate_suite_averages(results, component)
    
    # Kontrolleri yap
    check_results = {}
    
    # ASCE 7-16 kontrolü
    if "asce_7_16" in checks:
        asce_params = checks["asce_7_16"]
        check_results["asce_7_16"] = check_asce_7_16_compliance(
            suite_average, target_spectrum, T_design,
            asce_params.get("threshold_ratio", 0.9),
            asce_params.get("band_range", (0.2, 2.0))
        )
    
    # TBDY kontrolü
    if "tbdy" in checks:
        tbdy_params = checks["tbdy"]
        check_results["tbdy"] = check_tbdy_compliance(
            suite_average, target_spectrum, T_design,
            tbdy_params.get("threshold_ratio", 0.9),
            tbdy_params.get("band_range", (0.2, 1.5))
        )
    
    # Spektral şekil kontrolü
    if "spectral_shape" in checks:
        shape_params = checks["spectral_shape"]
        check_results["spectral_shape"] = check_spectral_shape_compliance(
            suite_average, target_spectrum, T_design,
            shape_params.get("shape_tolerance", 0.1)
        )
    
    return check_results


def create_default_checks() -> Dict[str, Any]:
    """
    Varsayılan kontrol parametrelerini oluşturur.
    
    Returns:
        Dict[str, Any]: Varsayılan kontrol parametreleri
    """
    return {
        "asce_7_16": {
            "threshold_ratio": 0.9,
            "band_range": (0.2, 2.0)
        },
        "tbdy": {
            "threshold_ratio": 0.9,
            "band_range": (0.2, 1.5)
        },
        "spectral_shape": {
            "shape_tolerance": 0.1
        }
    }


# Test fonksiyonu
if __name__ == "__main__":
    from .scale_3d import ScaleResult3D
    from .period_grid import build_period_grid
    
    # Test verisi oluştur
    T = build_period_grid()
    n_records = 5
    
    # Sahte sonuçlar oluştur
    results = []
    for i in range(n_records):
        result = ScaleResult3D(
            f=0.5 + i * 0.2,
            mse=0.1 + i * 0.05,
            SA_FN_scaled=np.ones_like(T) * (0.2 + i * 0.1),
            SA_FP_scaled=np.ones_like(T) * (0.3 + i * 0.1),
            SA_V_scaled=np.ones_like(T) * (0.25 + i * 0.1),
            SA_GM=np.ones_like(T) * (0.25 + i * 0.1),
            T_grid=T
        )
        results.append(result)
    
    # Hedef spektrum
    target_spectrum = 0.4 * np.ones_like(T)
    T_design = 1.0
    
    # Test 1: Suite ortalaması
    suite_average = calculate_suite_averages(results, component="GM")
    print(f"Suite ortalaması hesaplandı: {len(suite_average.arithmetic_mean)} nokta")
    print(f"İlk değer: {suite_average.arithmetic_mean[0]:.6f}")
    
    # Test 2: ASCE 7-16 kontrolü
    asce_check = check_asce_7_16_compliance(
        suite_average, target_spectrum, T_design
    )
    print(f"\nASCE 7-16 kontrolü: {asce_check.passed}")
    print(f"Mesaj: {asce_check.message}")
    
    # Test 3: TBDY kontrolü
    tbdy_check = check_tbdy_compliance(
        suite_average, target_spectrum, T_design
    )
    print(f"\nTBDY kontrolü: {tbdy_check.passed}")
    print(f"Mesaj: {tbdy_check.message}")
    
    # Test 4: Spektral şekil kontrolü
    shape_check = check_spectral_shape_compliance(
        suite_average, target_spectrum, T_design
    )
    print(f"\nSpektral şekil kontrolü: {shape_check.passed}")
    print(f"Mesaj: {shape_check.message}")
    
    # Test 5: Kapsamlı kontroller
    comprehensive_checks = perform_comprehensive_regulatory_checks(
        results, target_spectrum, T_design, component="GM"
    )
    print(f"\nKapsamlı kontroller:")
    for check_name, check_result in comprehensive_checks.items():
        print(f"{check_name}: {check_result.passed} - {check_result.message}")
    
    # Test 6: Varsayılan kontroller
    default_checks = create_default_checks()
    print(f"\nVarsayılan kontroller: {default_checks}")
