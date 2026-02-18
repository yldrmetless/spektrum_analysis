"""
3B Ölçekleme Ana Modülü
=====================

FN/FP/V bileşenleri için 3B ölçekleme işlemleri.
PEER ve TBDY-2018 uyumlu SRSS tabanlı ölçekleme.
"""

import numpy as np
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from .period_grid import build_period_grid
from .weight_function import create_uniform_weights
from .scale_factor import (
    calculate_scale_factor_3d,
    calculate_geometric_mean_spectrum,
    calculate_srss_spectrum,
    calculate_mse_log_space
)


@dataclass
class ScaleResult3D:
    """3B ölçekleme sonuçları."""
    f: float                           # Ölçek katsayısı
    mse: float                         # MSE değeri
    SA_FN_scaled: np.ndarray          # Ölçeklenmiş FN spektrum
    SA_FP_scaled: np.ndarray          # Ölçeklenmiş FP spektrum
    SA_V_scaled: Optional[np.ndarray] # Ölçeklenmiş V spektrum (varsa)
    SA_composite: np.ndarray          # Kullanılan bileşke spektrum (SRSS veya GM)
    T_grid: np.ndarray                # Periyot ızgarası
    spectral_ordinate: str            # Kullanılan metot (SRSS/GM)


def scale_record_3d(
    SA_target: np.ndarray,
    SA_FN: np.ndarray,
    SA_FP: np.ndarray,
    SA_V: Optional[np.ndarray] = None,
    weights: Optional[np.ndarray] = None,
    mode: str = "range",
    T_s: Optional[float] = None,
    T_grid: Optional[np.ndarray] = None,
    limits: Optional[Tuple[float, float]] = None,
    *,
    spectral_ordinate: str = "SRSS",
) -> ScaleResult3D:
    """
    3B ölçekleme gerçekleştirir.
    
    Args:
        SA_target: Hedef spektral ivme dizisi (301 nokta)
        SA_FN: Fault-Normal spektral ivme dizisi (301 nokta)
        SA_FP: Fault-Parallel spektral ivme dizisi (301 nokta)
        SA_V: Düşey spektral ivme dizisi (301 nokta, opsiyonel)
        weights: Ağırlık fonksiyonu (301 nokta, varsayılan: uniform)
        mode: "single" veya "range"
        T_s: Tek periyot modu için hedef periyot
        T_grid: Periyot ızgarası (varsayılan: 301 nokta)
        limits: Ölçek katsayısı sınırları
        
    Returns:
        ScaleResult3D: Ölçekleme sonuçları
    """
    # Varsayılan değerler
    if T_grid is None:
        T_grid = build_period_grid()
    
    if weights is None:
        weights = create_uniform_weights(T_grid)
    
    # Giriş doğrulama
    if len(SA_target) != 301:
        raise ValueError(f"Hedef spektrum 301 nokta olmalı, {len(SA_target)} bulundu")
    
    if len(SA_FN) != 301:
        raise ValueError(f"FN spektrum 301 nokta olmalı, {len(SA_FN)} bulundu")
    
    if len(SA_FP) != 301:
        raise ValueError(f"FP spektrum 301 nokta olmalı, {len(SA_FP)} bulundu")
    
    if SA_V is not None and len(SA_V) != 301:
        raise ValueError(f"V spektrum 301 nokta olmalı, {len(SA_V)} bulundu")
    
    if len(weights) != 301:
        raise ValueError(f"Ağırlık fonksiyonu 301 nokta olmalı, {len(weights)} bulundu")
    
    # 3B ölçek katsayısı hesapla (GM/SRSS seçilebilir)
    f, mse, SA_composite = calculate_scale_factor_3d(
        SA_target, SA_FN, SA_FP, weights, mode, T_s, T_grid, limits,
        spectral_ordinate=spectral_ordinate,
    )
    
    # Bileşenleri ölçekle
    SA_FN_scaled = f * SA_FN
    SA_FP_scaled = f * SA_FP
    SA_V_scaled = f * SA_V if SA_V is not None else None
    
    return ScaleResult3D(
        f=f,
        mse=mse,
        SA_FN_scaled=SA_FN_scaled,
        SA_FP_scaled=SA_FP_scaled,
        SA_V_scaled=SA_V_scaled,
        SA_composite=SA_composite,
        T_grid=T_grid,
        spectral_ordinate=str(spectral_ordinate).upper()
    )


def scale_multiple_records_3d(
    SA_target: np.ndarray,
    records_data: list[Dict[str, Any]],
    weights: Optional[np.ndarray] = None,
    mode: str = "range",
    T_s: Optional[float] = None,
    T_grid: Optional[np.ndarray] = None,
    limits: Optional[Tuple[float, float]] = None,
    *,
    spectral_ordinate: str = "SRSS",
) -> list[ScaleResult3D]:
    """
    Birden fazla kayıt için 3B ölçekleme gerçekleştirir.
    
    Args:
        SA_target: Hedef spektral ivme dizisi
        records_data: Kayıt verileri listesi
            Her kayıt: {"SA_FN": array, "SA_FP": array, "SA_V": array (opsiyonel), "metadata": dict}
        weights: Ağırlık fonksiyonu
        mode: "single" veya "range"
        T_s: Tek periyot modu için hedef periyot
        T_grid: Periyot ızgarası
        limits: Ölçek katsayısı sınırları
        
    Returns:
        list[ScaleResult3D]: Her kayıt için ölçekleme sonuçları
    """
    results = []
    
    for record in records_data:
        SA_FN = record["SA_FN"]
        SA_FP = record["SA_FP"]
        SA_V = record.get("SA_V", None)
        
        result = scale_record_3d(
            SA_target, SA_FN, SA_FP, SA_V, weights, mode, T_s, T_grid, limits,
            spectral_ordinate=spectral_ordinate,
        )
        
        results.append(result)
    
    return results


def calculate_suite_statistics(
    results: list[ScaleResult3D],
    component: str = "GM"
) -> Dict[str, Any]:
    """
    Suite istatistiklerini hesaplar.
    
    Args:
        results: Ölçekleme sonuçları listesi
        component: "FN", "FP", "V", "GM"
        
    Returns:
        Dict[str, Any]: Suite istatistikleri
    """
    if not results:
        return {}
    
    n_records = len(results)
    T_grid = results[0].T_grid
    
    # Bileşen seçimi
    if component == "FN":
        spectra = [r.SA_FN_scaled for r in results]
    elif component == "FP":
        spectra = [r.SA_FP_scaled for r in results]
    elif component == "V":
        spectra = [r.SA_V_scaled for r in results if r.SA_V_scaled is not None]
        if not spectra:
            return {"error": "Düşey bileşen verisi yok"}
    elif component == "GM":
        spectra = [r.SA_composite for r in results]
    else:
        raise ValueError(f"Bilinmeyen bileşen: {component}")
    
    if not spectra:
        return {"error": "Spektrum verisi yok"}
    
    # Ortalamalar
    spectra_array = np.array(spectra)
    
    # Aritmetik ortalama
    arithmetic_mean = np.mean(spectra_array, axis=0)
    
    # Geometrik ortalama
    geometric_mean = np.exp(np.mean(np.log(spectra_array), axis=0))
    
    # Standart sapma
    std_dev = np.std(spectra_array, axis=0)
    
    # Koeffisient of variation
    cv = std_dev / arithmetic_mean
    
    # MSE istatistikleri
    mse_values = [r.mse for r in results]
    mse_mean = np.mean(mse_values)
    mse_std = np.std(mse_values)
    
    # Ölçek katsayısı istatistikleri
    f_values = [r.f for r in results]
    f_mean = np.mean(f_values)
    f_std = np.std(f_values)
    f_min = np.min(f_values)
    f_max = np.max(f_values)
    
    return {
        "n_records": n_records,
        "component": component,
        "T_grid": T_grid,
        "arithmetic_mean": arithmetic_mean,
        "geometric_mean": geometric_mean,
        "std_dev": std_dev,
        "cv": cv,
        "mse_mean": mse_mean,
        "mse_std": mse_std,
        "f_mean": f_mean,
        "f_std": f_std,
        "f_min": f_min,
        "f_max": f_max,
        "f_values": f_values,
        "mse_values": mse_values
    }


def rank_records_by_mse(results: list[ScaleResult3D]) -> list[Tuple[int, ScaleResult3D]]:
    """
    Kayıtları MSE'ye göre sıralar.
    
    Args:
        results: Ölçekleme sonuçları listesi
        
    Returns:
        list[Tuple[int, ScaleResult3D]]: (sıra, sonuç) çiftleri
    """
    # MSE'ye göre sırala
    ranked = sorted(enumerate(results), key=lambda x: x[1].mse)
    return ranked


def select_top_records(
    results: list[ScaleResult3D],
    n_top: int = 10
) -> list[ScaleResult3D]:
    """
    En iyi N kaydı seçer.
    
    Args:
        results: Ölçekleme sonuçları listesi
        n_top: Seçilecek kayıt sayısı
        
    Returns:
        list[ScaleResult3D]: En iyi N kayıt
    """
    ranked = rank_records_by_mse(results)
    return [result for _, result in ranked[:n_top]]


# Test fonksiyonu
if __name__ == "__main__":
    from .period_grid import build_period_grid
    from .weight_function import create_uniform_weights
    
    # Test verisi oluştur
    T = build_period_grid()
    SA_target = 0.4 * np.ones_like(T)
    weights = create_uniform_weights(T)
    
    # Test 1: Tek kayıt 3B ölçekleme
    SA_FN = 0.2 * np.ones_like(T)
    SA_FP = 0.3 * np.ones_like(T)
    SA_V = 0.25 * np.ones_like(T)
    
    result = scale_record_3d(
        SA_target, SA_FN, SA_FP, SA_V, weights, mode="range", T_grid=T
    )
    
    print(f"Ölçek katsayısı: {result.f:.6f}")
    print(f"MSE: {result.mse:.6f}")
    print(f"FN ilk değer: {result.SA_FN_scaled[0]:.6f}")
    print(f"FP ilk değer: {result.SA_FP_scaled[0]:.6f}")
    print(f"V ilk değer: {result.SA_V_scaled[0]:.6f}")
    
    # Test 2: Çoklu kayıt
    records_data = [
        {"SA_FN": 0.2 * np.ones_like(T), "SA_FP": 0.3 * np.ones_like(T), "SA_V": 0.25 * np.ones_like(T)},
        {"SA_FN": 0.15 * np.ones_like(T), "SA_FP": 0.25 * np.ones_like(T), "SA_V": 0.2 * np.ones_like(T)},
        {"SA_FN": 0.3 * np.ones_like(T), "SA_FP": 0.35 * np.ones_like(T), "SA_V": 0.3 * np.ones_like(T)}
    ]
    
    results = scale_multiple_records_3d(
        SA_target, records_data, weights, mode="range", T_grid=T
    )
    
    print(f"\nÇoklu kayıt sonuçları:")
    for i, result in enumerate(results):
        print(f"Kayıt {i+1}: f={result.f:.6f}, MSE={result.mse:.6f}")
    
    # Test 3: Suite istatistikleri
    stats = calculate_suite_statistics(results, component="GM")
    print(f"\nSuite istatistikleri:")
    print(f"Kayıt sayısı: {stats['n_records']}")
    print(f"Ortalama MSE: {stats['mse_mean']:.6f}")
    print(f"Ortalama f: {stats['f_mean']:.6f}")
    print(f"f aralığı: {stats['f_min']:.6f} - {stats['f_max']:.6f}")
    
    # Test 4: Sıralama
    ranked = rank_records_by_mse(results)
    print(f"\nMSE sıralaması:")
    for rank, (idx, result) in enumerate(ranked):
        print(f"Sıra {rank+1}: Kayıt {idx+1}, MSE={result.mse:.6f}")
    
    # Test 5: En iyi kayıtlar
    top_records = select_top_records(results, n_top=2)
    print(f"\nEn iyi 2 kayıt:")
    for i, result in enumerate(top_records):
        print(f"Kayıt {i+1}: f={result.f:.6f}, MSE={result.mse:.6f}")
