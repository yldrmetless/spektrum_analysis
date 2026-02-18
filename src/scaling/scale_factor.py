"""
3B Ölçekleme için Ölçek Katsayısı Hesaplama Modülü
================================================

Tek periyot ve aralık ölçekleme için ölçek katsayısı hesaplama.
PGMD uyumlu kapalı form çözümler.
"""

import numpy as np
from typing import Tuple, Optional, Union
from .period_grid import build_period_grid


def spectrum_component(SA_FN: np.ndarray, SA_FP: np.ndarray, mode: str = "SRSS") -> np.ndarray:
    """
    İki yatay bileşenden bileşke spektrumu üretir.

    Args:
        SA_FN: Fault-Normal spektrumu
        SA_FP: Fault-Parallel spektrumu
        mode: "SRSS" veya "GM"

    Returns:
        np.ndarray: Bileşke spektrum
    """
    m = (mode or "").strip().lower()
    if m == "srss":
        # SA_SRSS = √(SA_FN² + SA_FP²)
        return np.sqrt(np.maximum(SA_FN, 0.0) ** 2 + np.maximum(SA_FP, 0.0) ** 2)
    elif m == "gm":
        # SA_GM = √(SA_FN × SA_FP)
        eps = 1e-15
        return np.sqrt(np.maximum(SA_FN, eps) * np.maximum(SA_FP, eps))
    else:
        raise ValueError("mode must be 'SRSS' or 'GM'")


def _interp_logT(values_T: np.ndarray, values_SA: np.ndarray, T_grid: np.ndarray) -> np.ndarray:
    """Log(T)-ln(SA) uzayında lineer interpolasyon, PGMD uyumlu."""
    eps = 1e-15
    x = np.log(np.maximum(values_T, eps))
    xi = np.log(np.maximum(T_grid, eps))
    y = np.log(np.maximum(values_SA, eps))
    yi = np.interp(xi, x, y)
    return np.exp(yi)


def mse_pgmd(
    SA_target: np.ndarray,
    SA_FN: np.ndarray,
    SA_FP: np.ndarray,
    T_input: np.ndarray,
    T_grid: np.ndarray,
    w: np.ndarray,
    f: float = 1.0,
    *,
    mode: str = "SRSS",
) -> float:
    """
    PGMD (PEER) tanımına uygun MSE hesaplar.

    MSE = Σ w(T_i) · [ ln(SA_target(T_i)) − ln(f · SA_rec(T_i)) ]^2  /  Σ w(T_i)

    Notlar:
    - T_grid: 0.01–10 s log-uzayında 301 nokta olmalı
    - w: log(T)'de interpolasyon sonrası [0,1], toplamı 1 olacak şekilde normalize
    - mode: "SRSS" veya "GM" (Spectral Ordinate seçimi)
    """
    SA_t = _interp_logT(T_input, SA_target, T_grid)
    SA_fn = _interp_logT(T_input, SA_FN, T_grid)
    SA_fp = _interp_logT(T_input, SA_FP, T_grid)
    SA_rec = spectrum_component(SA_fn, SA_fp, mode=mode)
    eps = 1e-15
    log_diff = np.log(np.maximum(SA_t, eps)) - np.log(np.maximum(f * SA_rec, eps))
    denom = float(np.sum(w)) if np.sum(w) > 0 else 1.0
    return float(np.sum(w * log_diff ** 2) / denom)


def _interpolate_loglog(T: np.ndarray, SA: np.ndarray, T_s: float) -> float:
    """
    Log-log interpolasyon (PEER/PGMD standart).
    
    Spektral ivme eğrileri log-normal dağılım gösterir, bu nedenle
    log(T) ve ln(SA) eksenlerinde lineer interpolasyon daha doğrudur.
    
    Args:
        T: Periyot dizisi
        SA: Spektral ivme dizisi
        T_s: Hedef periyot (tek nokta)
        
    Returns:
        float: Interpolasyon edilmiş SA(T_s) değeri
        
    Notes:
        - log(T) ekseninde: Periyotlar log-uzayda daha düzgün dağılır
        - ln(SA) ekseninde: Spektrumlar log-normal dağılım gösterir
        - Sıfır/negatif değerler: 1e-15 alt sınırı kullanılır
        
    References:
        PEER/PGMD §5.4.1 - Spectral interpolation in log-log space
    """
    # Sıfır/negatif değerleri koruma (log hesabı için)
    SA_safe = np.maximum(SA, 1e-15)
    
    # Log-log interpolasyon
    # log(T) ekseninde, ln(SA) ekseninde lineer
    ln_SA_interp = np.interp(
        np.log(T_s),           # log(T_s)
        np.log(T),             # log(T_grid)
        np.log(SA_safe)        # ln(SA)
    )
    
    # Gerçek değere dönüştür
    SA_Ts = np.exp(ln_SA_interp)
    
    return float(SA_Ts)


def calculate_single_period_scale_factor(
    SA_target: np.ndarray,
    SA_record: np.ndarray,
    T_grid: np.ndarray,
    T_s: float
) -> float:
    """
    Tek periyot ölçekleme için ölçek katsayısı hesaplar.
    
    PEER/PGMD Uyumlu: Log-log interpolasyon kullanır.
    
    Args:
        SA_target: Hedef spektral ivme dizisi (301 nokta)
        SA_record: Kayıt spektral ivme dizisi (301 nokta)
        T_grid: Periyot ızgarası (301 nokta)
        T_s: Hedef periyot (s)
        
    Returns:
        float: Ölçek katsayısı f = SA_target(T_s) / SA_record(T_s)
        
    Notes:
        - Log-log interpolasyon kullanılır (PEER standart)
        - Spektrumlar log-normal dağılım gösterir
        - Linear interpolasyon yerine log-log daha doğrudur
        
    References:
        PEER/PGMD §5.4.1 - Single period scaling
        
    Examples:
        >>> f = calculate_single_period_scale_factor(SA_tgt, SA_rec, T, T_s=1.0)
    """
    # T_s noktasında log-log interpolasyon (PEER uyumlu)
    SA_target_Ts = _interpolate_loglog(T_grid, SA_target, T_s)
    SA_record_Ts = _interpolate_loglog(T_grid, SA_record, T_s)
    
    if SA_record_Ts <= 0:
        raise ValueError(f"T_s={T_s} noktasında kayıt spektrumu sıfır veya negatif")
    
    f = SA_target_Ts / SA_record_Ts
    return float(f)


def calculate_range_scale_factor(
    SA_target: np.ndarray,
    SA_record: np.ndarray,
    weights: np.ndarray
) -> float:
    """
    Aralık ölçekleme için kapalı form ölçek katsayısı hesaplar.
    
    MSE'yi minimize eden kapalı form çözüm:
    ln(f) = Σ(w_i * ln(SA_target_i / SA_record_i)) / Σ(w_i)
    
    Args:
        SA_target: Hedef spektral ivme dizisi (301 nokta)
        SA_record: Kayıt spektral ivme dizisi (301 nokta)
        weights: Ağırlık fonksiyonu (301 nokta, toplam = 1)
        
    Returns:
        float: Ölçek katsayısı f
        
    Notes:
        - Sıfır/negatif değerler eps=1e-15 ile korunur (sayısal kararlılık)
        - Log hesabı için güvenlik taban değeri
        
    References:
        PEER/PGMD §5.4.2 - Range scaling with MSE minimization
    """
    # Sayısal güvenlik: Sıfır/negatif değerleri eps ile koru
    eps = 1e-15
    SA_target_safe = np.maximum(SA_target, eps)
    SA_record_safe = np.maximum(SA_record, eps)
    
    # Log-uzayda oran hesapla
    log_ratio = np.log(SA_target_safe) - np.log(SA_record_safe)
    
    # Ağırlıklı ortalama
    ln_f = np.sum(weights * log_ratio) / np.sum(weights)
    
    f = np.exp(ln_f)
    return float(f)


def calculate_mse_log_space(
    SA_target: np.ndarray,
    SA_scaled: np.ndarray,
    weights: np.ndarray
) -> float:
    """
    Log-uzayda MSE hesaplar.
    
    MSE = Σ(w_i * [ln(SA_target_i) - ln(SA_scaled_i)]²) / Σ(w_i)
    
    Args:
        SA_target: Hedef spektral ivme dizisi
        SA_scaled: Ölçeklenmiş spektral ivme dizisi
        weights: Ağırlık fonksiyonu
        
    Returns:
        float: MSE değeri
        
    Notes:
        - Sıfır/negatif değerler eps=1e-15 ile korunur (log(0) tanımsız)
        - Sayısal kararlılık için güvenlik taban değeri
        - Gerçek spektrumlarda SA > 0 olmalı, ama koruma kritik
        
    References:
        PEER/PGMD §5.4.2 - MSE in log-space
        
    Examples:
        >>> mse = calculate_mse_log_space(SA_tgt, SA_scaled, weights)
    """
    # Sayısal güvenlik: log(0) koruması
    eps = 1e-15
    SA_target_safe = np.maximum(SA_target, eps)
    SA_scaled_safe = np.maximum(SA_scaled, eps)
    
    # Log-uzayda fark
    log_diff = np.log(SA_target_safe) - np.log(SA_scaled_safe)
    
    # Ağırlıklı MSE
    mse = np.sum(weights * log_diff**2) / np.sum(weights)
    
    return float(mse)


def apply_scale_limits(
    f: float,
    limits: Optional[Tuple[float, float]] = None
) -> float:
    """
    Ölçek katsayısına sınırlar uygular.
    
    Args:
        f: Ölçek katsayısı
        limits: (min_f, max_f) sınırları
        
    Returns:
        float: Sınırlanmış ölçek katsayısı
    """
    if limits is None:
        return f
    
    f_min, f_max = limits
    return float(np.clip(f, f_min, f_max))


def calculate_scale_factor_and_mse(
    SA_target: np.ndarray,
    SA_record: np.ndarray,
    weights: np.ndarray,
    mode: str = "range",
    T_s: Optional[float] = None,
    T_grid: Optional[np.ndarray] = None,
    limits: Optional[Tuple[float, float]] = None
) -> Tuple[float, float]:
    """
    Verilen ağırlıklara göre ölçek katsayısı ve MSE hesaplar.
    Basitleştirilmiş üst-seviye yardımcı (Untitled-1 uyumlu API).
    """
    if T_grid is None:
        T_grid = build_period_grid()

    if mode == "single":
        if T_s is None:
            raise ValueError("Tek periyot modu için T_s (hedef periyot) gereklidir.")
        f = calculate_single_period_scale_factor(SA_target, SA_record, T_grid, T_s)
    elif mode == "range":
        f = calculate_range_scale_factor(SA_target, SA_record, weights)
    elif str(mode).lower() in {"no", "no_scaling", "noscaling"}:
        f = 1.0
    else:
        raise ValueError(f"Bilinmeyen ölçekleme modu: {mode}")

    f = apply_scale_limits(f, limits)
    SA_scaled = f * SA_record
    mse = calculate_mse_log_space(SA_target, SA_scaled, weights)
    return f, mse


def calculate_scale_factor(
    SA_target: np.ndarray,
    SA_record: np.ndarray,
    weights: np.ndarray,
    mode: str = "range",
    T_s: Optional[float] = None,
    T_grid: Optional[np.ndarray] = None,
    limits: Optional[Tuple[float, float]] = None
) -> Tuple[float, float]:
    """
    Ölçek katsayısı ve MSE hesaplar.
    
    Args:
        SA_target: Hedef spektral ivme dizisi (301 nokta)
        SA_record: Kayıt spektral ivme dizisi (301 nokta)
        weights: Ağırlık fonksiyonu (301 nokta)
        mode: "single" veya "range"
        T_s: Tek periyot modu için hedef periyot
        T_grid: Periyot ızgarası (varsayılan: 301 nokta)
        limits: Ölçek katsayısı sınırları
        
    Returns:
        Tuple[float, float]: (ölçek_katsayısı, MSE)
    """
    if T_grid is None:
        T_grid = build_period_grid()
    
    if mode == "single":
        if T_s is None:
            raise ValueError("Tek periyot modu için T_s gerekli")
        f = calculate_single_period_scale_factor(SA_target, SA_record, T_grid, T_s)
    elif mode == "range":
        f = calculate_range_scale_factor(SA_target, SA_record, weights)
    else:
        raise ValueError(f"Bilinmeyen mod: {mode}")
    
    # Sınırları uygula
    f = apply_scale_limits(f, limits)
    
    # MSE hesapla
    SA_scaled = f * SA_record
    mse = calculate_mse_log_space(SA_target, SA_scaled, weights)
    
    return f, mse


def calculate_geometric_mean_spectrum(
    SA_FN: np.ndarray,
    SA_FP: np.ndarray
) -> np.ndarray:
    """
    İki yatay bileşenin geometrik ortalamasını hesaplar.
    
    SA_GM = √(SA_FN * SA_FP)
    
    Args:
        SA_FN: Fault-Normal spektral ivme dizisi
        SA_FP: Fault-Parallel spektral ivme dizisi
        
    Returns:
        np.ndarray: Geometrik ortalama spektrum
    """
    # Negatif/sıfır değerler için güvenlik: teorik olarak SA > 0 olmalı
    return np.sqrt(np.maximum(SA_FN, 0.0) * np.maximum(SA_FP, 0.0))


def calculate_srss_spectrum(
    SA_FN: np.ndarray,
    SA_FP: np.ndarray
) -> np.ndarray:
    """
    TBDY-2018 uyumlu bileşke yatay spektrum (SRSS) hesaplar.
    
    SA_SRSS = √(SA_FN² + SA_FP²)
    
    Args:
        SA_FN: Fault-Normal spektral ivme dizisi
        SA_FP: Fault-Parallel spektral ivme dizisi
        
    Returns:
        np.ndarray: SRSS spektrum
    """
    return np.sqrt(SA_FN**2 + SA_FP**2)


def calculate_scale_factor_3d(
    SA_target: np.ndarray,
    SA_FN: np.ndarray,
    SA_FP: np.ndarray,
    weights: np.ndarray,
    mode: str = "range",
    T_s: Optional[float] = None,
    T_grid: Optional[np.ndarray] = None,
    limits: Optional[Tuple[float, float]] = None,
    *,
    spectral_ordinate: str = "SRSS",
) -> Tuple[float, float, np.ndarray]:
    """
    3B ölçekleme için ölçek katsayısı ve MSE hesaplar.

    Args:
        SA_target: Hedef spektral ivme dizisi
        SA_FN: Fault-Normal spektral ivme dizisi
        SA_FP: Fault-Parallel spektral ivme dizisi
        weights: Ağırlık fonksiyonu (∑w=1 önerilir)
        mode: "single", "range" veya "no_scaling"
        T_s: Tek periyot modu için hedef periyot
        T_grid: Periyot ızgarası
        limits: Ölçek katsayısı sınırları
        spectral_ordinate: "GM" veya "SRSS"

    Returns:
        Tuple[float, float, np.ndarray]: (ölçek_katsayısı f, MSE, seçilen bileşke spektrum)
    """
    # Bileşke spektrumu seç (GM veya SRSS)
    # Varsayılan: SRSS (TBDY ile uyumlu bileşke). No Scaling akışında PGMD için GM tercih edilebilir.
    ord_mode = (spectral_ordinate or "SRSS").strip().lower()
    if ord_mode == "gm":
        SA_MAIN = calculate_geometric_mean_spectrum(SA_FN, SA_FP)
    elif ord_mode == "srss":
        SA_MAIN = calculate_srss_spectrum(SA_FN, SA_FP)
    else:
        raise ValueError("spectral_ordinate must be 'GM' or 'SRSS'")

    # No Scaling: f=1.0 ve MSE'yi doğrudan hesapla
    if str(mode).lower() in {"no", "no_scaling", "noscaling"}:
        f = 1.0
        mse = calculate_mse_log_space(SA_target, f * SA_MAIN, weights)
        return f, mse, SA_MAIN

    # Diğer modlarda kapalı form hesapları kullan
    f, mse = calculate_scale_factor(
        SA_target, SA_MAIN, weights, mode, T_s, T_grid, limits
    )

    return f, mse, SA_MAIN


def calculate_scale_factor_3d_tbdy(
    SA_target: np.ndarray,
    SA_FN: np.ndarray,
    SA_FP: np.ndarray,
    weights: np.ndarray,
    T1: float,
    mode: str = "range",
    T_s: Optional[float] = None,
    T_grid: Optional[np.ndarray] = None,
    limits: Optional[Tuple[float, float]] = None
) -> Tuple[float, float, np.ndarray]:
    """
    TBDY-2018 uyumlu 3B ölçekleme için ölçek katsayısı hesaplar (SRSS tabanlı).
    
    TBDY 2.5.2.1-b: Bileşke yatay spektrum = √(SAx² + SAy²) (SRSS)
    
    Args:
        SA_target: Hedef spektral ivme dizisi
        SA_FN: Fault-Normal spektral ivme dizisi  
        SA_FP: Fault-Parallel spektral ivme dizisi
        weights: Ağırlık fonksiyonu
        T1: Birinci doğal periyot
        mode: "single" veya "range"
        T_s: Tek periyot modu için hedef periyot
        T_grid: Periyot ızgarası
        limits: Ölçek katsayısı sınırları
        
    Returns:
        Tuple[float, float, np.ndarray]: (ölçek_katsayısı, MSE, SA_SRSS)
    """
    if T_grid is None:
        T_grid = build_period_grid()
    
    # TBDY uyumlu SRSS hesapla
    SA_SRSS = calculate_srss_spectrum(SA_FN, SA_FP)
    
    # Ağırlıkları TBDY aralığına göre normalize et
    weights_normalized = normalize_weights_tbdy(weights, T_grid, T1)
    
    # SRSS üzerinden ölçek katsayısı hesapla
    f, mse = calculate_scale_factor(
        SA_target, SA_SRSS, weights_normalized, mode, T_s, T_grid, limits
    )
    
    return f, mse, SA_SRSS


def normalize_weights_tbdy(
    weights: np.ndarray,
    T_grid: np.ndarray,
    T1: float
) -> np.ndarray:
    """
    TBDY-2018 uyumlu ağırlık fonksiyonu normalizasyonu.
    
    Sadece [0.2*T1, 1.5*T1] aralığındaki ağırlıkları kullanır ve normalize eder.
    
    Args:
        weights: Orijinal ağırlık fonksiyonu
        T_grid: Periyot ızgarası
        T1: Birinci doğal periyot
        
    Returns:
        np.ndarray: Normalize edilmiş ağırlıklar
    """
    # Güvenli dizi dönüşümleri
    weights = np.asarray(weights, dtype=float)
    T_grid = np.asarray(T_grid, dtype=float)
    
    # TBDY aralığı [0.2*T1, 1.5*T1]
    T_min = 0.2 * float(T1)
    T_max = 1.5 * float(T1)
    mask = (T_grid >= T_min) & (T_grid <= T_max)
    
    # Maske dışını sıfırla, sonra normalize et (∑w=1)
    weights_norm = weights.copy()
    weights_norm[~mask] = 0.0
    s = float(weights_norm.sum())
    if s <= 0.0:
        raise ValueError("TBDY bandında ağırlıklar sıfırlandı.")
    return weights_norm / s


# Test fonksiyonu
if __name__ == "__main__":
    from .period_grid import build_period_grid
    from .weight_function import create_uniform_weights
    
    # Test verisi oluştur
    T = build_period_grid()
    SA_target = 0.4 * np.ones_like(T)  # Sabit hedef spektrum
    SA_record = 0.2 * np.ones_like(T)  # Sabit kayıt spektrum
    weights = create_uniform_weights(T)
    
    # Test 1: Tek periyot ölçekleme
    f_single, mse_single = calculate_scale_factor(
        SA_target, SA_record, weights, mode="single", T_s=1.0, T_grid=T
    )
    print(f"Tek periyot ölçek katsayısı: {f_single:.6f}")
    print(f"Tek periyot MSE: {mse_single:.6f}")
    
    # Test 2: Aralık ölçekleme
    f_range, mse_range = calculate_scale_factor(
        SA_target, SA_record, weights, mode="range", T_grid=T
    )
    print(f"Aralık ölçek katsayısı: {f_range:.6f}")
    print(f"Aralık MSE: {mse_range:.6f}")
    
    # Test 3: 3B ölçekleme
    SA_FN = 0.2 * np.ones_like(T)
    SA_FP = 0.3 * np.ones_like(T)
    f_3d, mse_3d, SA_GM = calculate_scale_factor_3d(
        SA_target, SA_FN, SA_FP, weights, mode="range", T_grid=T
    )
    print(f"3B ölçek katsayısı: {f_3d:.6f}")
    print(f"3B MSE: {mse_3d:.6f}")
    print(f"GM spektrum ilk değer: {SA_GM[0]:.6f}")
    
    # Test 4: Sınırlar
    f_limited, mse_limited = calculate_scale_factor(
        SA_target, SA_record, weights, mode="range", T_grid=T, limits=(0.5, 3.0)
    )
    print(f"Sınırlı ölçek katsayısı: {f_limited:.6f}")
    print(f"Sınırlı MSE: {mse_limited:.6f}")
