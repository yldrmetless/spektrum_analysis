"""
3B Ölçekleme için Ağırlık Fonksiyonu Modülü
===========================================

Kullanıcı tanımlı ağırlık fonksiyonlarını 301 noktalı ızgaraya interpolasyon
ve normalizasyon işlemleri.
"""

import numpy as np
from typing import Tuple, Optional, Union
from .period_grid import build_period_grid


def create_weight_function(
    period_knots: np.ndarray,
    weight_knots: np.ndarray,
    T_grid: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Kullanıcı tanımlı ağırlık fonksiyonunu 301 noktalı ızgaraya interpolasyon yapar.
    
    PEER Mantığı: Aralık dışındaki periyotlara ağırlık = 0
    
    Args:
        period_knots: Kullanıcı tanımlı periyot noktaları (artan sırada)
        weight_knots: Kullanıcı tanımlı ağırlık değerleri (≥ 0)
        T_grid: Hedef ızgara (varsayılan: 301 nokta)
        
    Returns:
        np.ndarray: Normalize edilmiş ağırlık fonksiyonu (toplam = 1)
        
    Notes:
        - Log-T ekseninde lineer interpolasyon (PEER/PGMD standart)
        - Aralık dışı (T < T_knots[0] veya T > T_knots[-1]) ağırlıklar 0
        - Normalize edilmiş: Σw = 1.0
        
    Examples:
        >>> # Tek periyot bandı
        >>> T_knots = np.array([0.1, 1.0, 5.0])
        >>> W_knots = np.array([0.0, 1.0, 0.0])  # 1.0s'de pik
        >>> w = create_weight_function(T_knots, W_knots)
        >>> # T < 0.1 ve T > 5.0 için w = 0
    """
    if T_grid is None:
        T_grid = build_period_grid()
    
    # Giriş doğrulama (toleranslı)
    if len(period_knots) != len(weight_knots):
        raise ValueError("Periyot ve ağırlık dizileri aynı uzunlukta olmalı")
    
    if len(period_knots) < 2:
        raise ValueError("En az 2 nokta gerekli")
    
    eps_t = 1e-12
    pk = np.asarray(period_knots, dtype=float)
    wk = np.asarray(weight_knots, dtype=float)
    order = np.argsort(pk)
    pk = pk[order]
    wk = wk[order]
    # Artan sırayı toleransla kontrol et; çok yakın düğümleri birleştir
    diffs = np.diff(pk)
    if not np.all(diffs > -eps_t):
        raise ValueError("Periyot dizisi artan sırada olmalı (yaklaşık)")
    keep_idx = [0]
    for i in range(1, len(pk)):
        if abs(pk[i] - pk[keep_idx[-1]]) > eps_t:
            keep_idx.append(i)
        else:
            wk[keep_idx[-1]] = (wk[keep_idx[-1]] + wk[i]) / 2.0
    pk = pk[keep_idx]
    wk = wk[keep_idx]
    
    if np.any(wk < 0):
        raise ValueError("Ağırlık değerleri negatif olamaz")
    
    # Log-uzayda interpolasyon (PEER/PGMD: log(T) ekseni doğal log ile)
    # Not: MSE hesapları ln(SA) kullandığı için tutarlılık açısından doğal log tercih edilir
    log_T_knots = np.log(pk)
    log_T_grid = np.log(T_grid)
    
    # Log-uzayda lineer interpolasyon
    # KRİTİK: Aralık dışı değerler 0 olmalı (PEER mantığı)
    w_interp = np.interp(log_T_grid, log_T_knots, wk, 
                         left=0.0, right=0.0)
    
    # Ek güvenlik: Negatif ağırlıkları 0 yap (olmamalı ama sayısal hata için)
    w_interp = np.clip(w_interp, 0.0, None)
    
    # Normalize et (toplam = 1)
    s = float(w_interp.sum())
    if s <= 0.0:
        raise ValueError("Ağırlık fonksiyonu ızgarada sıfıra indirgendi")
    w_normalized = w_interp / s
    # Epsilon düzeltmesi: toplam tam 1.0
    residual = 1.0 - float(np.sum(w_normalized))
    if abs(residual) > 0.0 and w_normalized.size > 0:
        try:
            imax = int(np.argmax(w_normalized))
            w_normalized[imax] = float(w_normalized[imax] + residual)
        except Exception:
            pass
    
    return w_normalized


def create_uniform_weights(T_grid: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Uniform ağırlık fonksiyonu oluşturur.
    
    Args:
        T_grid: Hedef ızgara (varsayılan: 301 nokta)
        
    Returns:
        np.ndarray: Uniform ağırlık fonksiyonu
    """
    if T_grid is None:
        T_grid = build_period_grid()
    
    n = len(T_grid)
    return np.ones(n) / n


def create_short_period_weights(
    T_grid: Optional[np.ndarray] = None,
    T_cutoff: float = 1.0,
    decay_factor: float = 2.0
) -> np.ndarray:
    """
    Kısa periyotlara ağırlık veren fonksiyon oluşturur.
    
    Args:
        T_grid: Hedef ızgara (varsayılan: 301 nokta)
        T_cutoff: Kesim periyodu (s)
        decay_factor: Çürüme faktörü (büyük değer = daha hızlı çürüme)
        
    Returns:
        np.ndarray: Kısa periyot ağırlıklı fonksiyon
    """
    if T_grid is None:
        T_grid = build_period_grid()
    
    # T_cutoff'tan sonra çürüyen ağırlık
    w = np.exp(-decay_factor * (T_grid - T_cutoff) / T_cutoff)
    w[T_grid <= T_cutoff] = 1.0
    
    # Normalize et
    return w / np.sum(w)


def create_long_period_weights(
    T_grid: Optional[np.ndarray] = None,
    T_cutoff: float = 1.0,
    growth_factor: float = 2.0
) -> np.ndarray:
    """
    Uzun periyotlara ağırlık veren fonksiyon oluşturur.
    
    Args:
        T_grid: Hedef ızgara (varsayılan: 301 nokta)
        T_cutoff: Kesim periyodu (s)
        growth_factor: Büyüme faktörü (büyük değer = daha hızlı büyüme)
        
    Returns:
        np.ndarray: Uzun periyot ağırlıklı fonksiyon
    """
    if T_grid is None:
        T_grid = build_period_grid()
    
    # T_cutoff'tan sonra büyüyen ağırlık
    w = np.exp(growth_factor * (T_grid - T_cutoff) / T_cutoff)
    w[T_grid <= T_cutoff] = 1.0
    
    # Normalize et
    return w / np.sum(w)


def create_band_weights(
    T_grid: Optional[np.ndarray] = None,
    T_center: float = 1.0,
    bandwidth: float = 0.5,
    shape: str = "gaussian"
) -> np.ndarray:
    """
    Belirli periyot bandına odaklanan ağırlık fonksiyonu oluşturur.
    
    Args:
        T_grid: Hedef ızgara (varsayılan: 301 nokta)
        T_center: Merkez periyot (s)
        bandwidth: Bant genişliği (s)
        shape: Şekil ("gaussian", "rectangular", "triangular")
        
    Returns:
        np.ndarray: Bant ağırlıklı fonksiyon
    """
    if T_grid is None:
        T_grid = build_period_grid()
    
    if shape == "gaussian":
        # Gaussian dağılım
        sigma = bandwidth / 2.355  # FWHM = 2.355 * sigma
        w = np.exp(-0.5 * ((T_grid - T_center) / sigma) ** 2)
    elif shape == "rectangular":
        # Dikdörtgen pencere
        w = np.zeros_like(T_grid)
        mask = np.abs(T_grid - T_center) <= bandwidth / 2
        w[mask] = 1.0
    elif shape == "triangular":
        # Üçgen pencere
        w = np.maximum(0, 1 - np.abs(T_grid - T_center) / (bandwidth / 2))
    else:
        raise ValueError(f"Bilinmeyen şekil: {shape}")
    
    # Normalize et
    return w / np.sum(w)


def validate_weight_function(w: np.ndarray, T_grid: np.ndarray) -> Tuple[bool, str]:
    """
    Ağırlık fonksiyonunun geçerliliğini kontrol eder.
    
    Args:
        w: Ağırlık fonksiyonu
        T_grid: Periyot ızgarası
        
    Returns:
        Tuple[bool, str]: (geçerli_mi, hata_mesajı)
    """
    if len(w) != len(T_grid):
        return False, f"Ağırlık uzunluğu ({len(w)}) periyot uzunluğu ({len(T_grid)}) ile eşleşmiyor"
    
    if np.any(w < 0):
        return False, "Negatif ağırlık değerleri var"
    
    if not np.allclose(np.sum(w), 1.0, rtol=1e-10):
        return False, f"Ağırlık toplamı 1.0 olmalı, {np.sum(w)} bulundu"
    
    if np.all(w == 0):
        return False, "Tüm ağırlıklar sıfır"
    
    return True, "Geçerli"


# Test fonksiyonu
if __name__ == "__main__":
    from .period_grid import build_period_grid
    
    T = build_period_grid()
    
    # Test 1: Uniform ağırlık
    w_uniform = create_uniform_weights(T)
    print(f"Uniform ağırlık toplamı: {np.sum(w_uniform):.10f}")
    
    # Test 2: Kullanıcı tanımlı ağırlık
    period_knots = np.array([0.1, 0.5, 1.0, 2.0, 5.0])
    weight_knots = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    w_custom = create_weight_function(period_knots, weight_knots, T)
    print(f"Özel ağırlık toplamı: {np.sum(w_custom):.10f}")
    
    # Test 3: Kısa periyot ağırlık
    w_short = create_short_period_weights(T, T_cutoff=1.0)
    print(f"Kısa periyot ağırlık toplamı: {np.sum(w_short):.10f}")
    
    # Test 4: Bant ağırlık
    w_band = create_band_weights(T, T_center=1.0, bandwidth=0.5)
    print(f"Bant ağırlık toplamı: {np.sum(w_band):.10f}")
    
    # Doğrulama
    is_valid, message = validate_weight_function(w_custom, T)
    print(f"Doğrulama: {message}")
