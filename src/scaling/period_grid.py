"""
3B Ölçekleme için Periyot Izgarası Modülü
==========================================

PGMD uyumlu log-uzay periyot ızgarası oluşturma.
0.01-10 s aralığında, dekad başına 100 nokta, toplam 301 nokta.
"""

import numpy as np
from typing import Tuple


def build_period_grid() -> np.ndarray:
    """
    PGMD uyumlu log-uzay periyot ızgarası oluşturur.
    
    Returns:
        np.ndarray: 0.01-10 s aralığında log-eşit aralıklı 301 nokta
    """
    # 0.01-10 s aralığında ln-uzayda 301 nokta (geomspace)
    # Dekad başına 100 nokta (0.01-0.1, 0.1-1.0, 1.0-10.0)
    T = np.geomspace(0.01, 10.0, 301)
    
    return T


def validate_period_grid(T: np.ndarray) -> Tuple[bool, str]:
    """
    Periyot ızgarasının PGMD gereksinimlerini karşılayıp karşılamadığını kontrol eder.
    
    Args:
        T: Kontrol edilecek periyot dizisi
        
    Returns:
        Tuple[bool, str]: (geçerli_mi, hata_mesajı)
    """
    if len(T) != 301:
        return False, f"Periyot sayısı 301 olmalı, {len(T)} bulundu"
    
    if not np.allclose(T[0], 0.01, rtol=1e-6):
        return False, f"İlk periyot 0.01 s olmalı, {T[0]} bulundu"
    
    if not np.allclose(T[-1], 10.0, rtol=1e-6):
        return False, f"Son periyot 10.0 s olmalı, {T[-1]} bulundu"
    
    # Log-uzayda eşit aralıklı olup olmadığını kontrol et
    log_T = np.log10(T)
    log_diff = np.diff(log_T)
    if not np.allclose(log_diff, log_diff[0], rtol=1e-10):
        return False, "Log-uzayda eşit aralıklı değil"
    
    return True, "Geçerli"


def interpolate_to_grid(
    T_input: np.ndarray, 
    SA_input: np.ndarray, 
    T_grid: np.ndarray
) -> np.ndarray:
    """
    Verilen periyot-spektrum çiftini standart ızgaraya log-log interpolasyon yapar.
    
    PEER/PGMD Standart: Spektrumlar log-normal dağılım gösterir, bu nedenle
    log(T) ve ln(SA) eksenlerinde lineer interpolasyon kullanılır.
    
    Args:
        T_input: Giriş periyot dizisi
        SA_input: Giriş spektral ivme dizisi
        T_grid: Hedef ızgara (301 nokta)
        
    Returns:
        np.ndarray: T_grid üzerinde interpolasyon yapılmış SA değerleri
        
    Notes:
        - log(T) ekseninde interpolasyon: Periyotlar log-uzayda düzgün
        - ln(SA) ekseninde interpolasyon: Spektrumlar log-normal
        - Sıfır/negatif değerler 1e-15 ile korunur
        - MSE hesabı ile tutarlı (MSE de ln(SA) kullanıyor)
        
    References:
        PEER/PGMD §5.4.1 - Spectral interpolation in log-log space
        
    Examples:
        >>> SA_301 = interpolate_to_grid(T_raw, SA_raw, T_grid_301)
    """
    # Sıfır/negatif değerleri koruma (log hesabı için)
    SA_safe = np.maximum(SA_input, 1e-15)
    T_safe = np.maximum(T_input, 1e-15)
    T_grid_safe = np.maximum(T_grid, 1e-15)
    
    # Log-log interpolasyon (PEER/PGMD standart)
    # log(T) ekseninde, ln(SA) ekseninde lineer interpolasyon
    ln_SA_grid = np.interp(
        np.log(T_grid_safe),    # log(T_grid) - natural log
        np.log(T_safe),         # log(T_input)
        np.log(SA_safe)         # ln(SA_input) - natural log
    )
    
    # Gerçek değerlere dönüştür
    SA_grid = np.exp(ln_SA_grid)
    
    return SA_grid


def get_period_indices(T_grid: np.ndarray, T_range: Tuple[float, float]) -> np.ndarray:
    """
    Belirli periyot aralığındaki indeksleri döndürür.
    
    Args:
        T_grid: Periyot ızgarası
        T_range: (T_min, T_max) aralığı
        
    Returns:
        np.ndarray: Aralık içindeki indeksler
    """
    T_min, T_max = T_range
    mask = (T_grid >= T_min) & (T_grid <= T_max)
    return np.where(mask)[0]


# Test fonksiyonu
if __name__ == "__main__":
    # Test periyot ızgarası oluşturma
    T = build_period_grid()
    print(f"Periyot ızgarası oluşturuldu: {len(T)} nokta")
    print(f"İlk periyot: {T[0]:.4f} s")
    print(f"Son periyot: {T[-1]:.4f} s")
    
    # Doğrulama
    is_valid, message = validate_period_grid(T)
    print(f"Doğrulama: {message}")
    
    # Log-uzayda eşit aralıklı olduğunu kontrol et
    log_T = np.log10(T)
    log_diff = np.diff(log_T)
    print(f"Log-uzay aralığı: {log_diff[0]:.6f}")
    print(f"Tüm aralıklar eşit mi: {np.allclose(log_diff, log_diff[0])}")
