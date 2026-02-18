"""
TBDY-2018 3B Basit Ölçeklendirme Modülü
=====================================

TBDY-2018 Bölüm 2.5'e uygun 3B basit ölçeklendirme algoritması.
- Bileşke yatay spektrum (SRSS) hesaplama
- PEER uyumlu kapalı form ölçek katsayısı
- Global gamma düzeltmesi (1.30 koşulu)
- Kayıt validasyonu
"""

import numpy as np
from typing import List, Tuple, Dict, Any, Optional, Sequence
from dataclasses import dataclass

from .scale_factor import (
    calculate_srss_spectrum, 
    normalize_weights_tbdy,
    calculate_range_scale_factor,
    calculate_mse_log_space
)
from .period_grid import build_period_grid
from .weight_function import create_uniform_weights


@dataclass
class TBDYScaleResult:
    """TBDY-2018 uyumlu 3B ölçeklendirme sonuçları."""
    # Kayıt bazlı sonuçlar
    f_list: List[float]                    # Her kayıt için ölçek katsayısı
    mse_list: List[float]                  # Her kayıt için MSE
    srss_scaled_list: List[np.ndarray]     # Her kayıt için ölçeklenmiş SRSS spektrumu
    
    # Ortalama sonuçlar
    srss_avg: np.ndarray                   # Ortalama ölçeklenmiş SRSS spektrumu
    target_spectrum: np.ndarray            # Hedef spektrum (1.30 × S_design)
    T_grid: np.ndarray                     # Periyot ızgarası
    
    # TBDY kontrolü
    min_ratio: float                       # Minimum oran (ortalama / 1.30×S_design)
    pass_tbdy: bool                        # TBDY koşulunu sağlıyor mu?
    
    # Global gamma düzeltmesi
    global_gamma: float                    # Global düzeltme katsayısı
    gamma_applied: bool                    # Global gamma uygulandı mı?
    
    # Validasyon
    n_records: int                         # Kayıt sayısı
    same_event_check: bool                 # Aynı olay kuralı sağlanıyor mu?
    
    # Periyot aralığı
    T1: float                              # Birinci doğal periyot
    T_range: Tuple[float, float]           # Kontrol aralığı [0.2×T1, 1.5×T1]

    # Opsiyonel: global gamma sonrası uygulanan f listesi
    f_applied_list: Optional[List[float]] = None  # Global gamma uygulandıysa (base * gamma)


def validate_records_tbdy(
    records: Sequence[Tuple[np.ndarray, np.ndarray, float, Dict]],
    min_records: int = 11,
    max_same_event: int = 4
) -> Tuple[bool, str]:
    """
    TBDY-2018 kayıt validasyonu.
    
    Args:
        records: Kayıt listesi [(ax, ay, dt, meta), ...]
        min_records: Minimum kayıt sayısı
        max_same_event: Aynı olay maksimum kayıt sayısı
        
    Returns:
        Tuple[bool, str]: (geçerli_mi, hata_mesajı)
    """
    n_records = len(records)
    
    # Aynı olay kontrolü
    event_counts = {}
    for i, (ax, ay, dt, meta) in enumerate(records):
        event_id = meta.get("event_id") or meta.get("group_id") or f"event_{i//3}"
        event_counts[event_id] = event_counts.get(event_id, 0) + 1
        
        if event_counts[event_id] > max_same_event:
            return False, f"Aynı olay ({event_id}) için çok fazla kayıt: {event_counts[event_id]} > {max_same_event} (TBDY 2.5.1.3)"

    # Kayıt sayısı kontrolü (aynı olay ihlali yoksa değerlendirilir)
    if n_records < min_records:
        return False, f"Kayıt sayısı yetersiz: {n_records} < {min_records} (TBDY 2.5.1.3)"
    
    return True, "Validasyon başarılı"


def compute_srss_spectra(
    records: Sequence[Tuple[np.ndarray, np.ndarray, float, Dict]],
    T_grid: np.ndarray,
    damping: float = 5.0
) -> List[np.ndarray]:
    """
    Her kayıt için SRSS spektrumu hesaplar.
    
    Args:
        records: Kayıt listesi
        T_grid: Periyot ızgarası
        damping: Sönüm oranı (%)
        
    Returns:
        List[np.ndarray]: SRSS spektrumları listesi
    """
    from ..calculations.response_spectrum import compute_elastic_response_spectrum, SpectrumSettings
    
    settings = SpectrumSettings(
        damping_list=(damping,),
        Tmin=float(T_grid.min()),
        Tmax=float(T_grid.max()),
        nT=len(T_grid),
        logspace=True,
        accel_unit="g",
        baseline="linear"
    )
    
    srss_list = []
    for ax, ay, dt, meta in records:
        time = np.arange(len(ax)) * dt
        
        # X bileşeni spektrumu
        spec_x = compute_elastic_response_spectrum(time, ax, settings)
        curves_x = next(iter(spec_x.values()))
        
        # Y bileşeni spektrumu  
        spec_y = compute_elastic_response_spectrum(time, ay, settings)
        curves_y = next(iter(spec_y.values()))
        
        # Periyot ızgarasına interpolasyon
        def safe_interp(src_T, src_Sa, tgt_T):
            """Log(T)-ln(SA) uzayında güvenli interpolasyon (PGMD uyumlu)."""
            src_T = np.asarray(src_T, dtype=float)
            src_Sa = np.asarray(src_Sa, dtype=float)
            tgt_T = np.asarray(tgt_T, dtype=float)
            eps = 1e-15
            order = np.argsort(src_T)
            xlog = np.log(np.maximum(src_T[order], eps))
            ylog = np.log(np.maximum(src_Sa[order], eps))
            xi = np.log(np.maximum(tgt_T, eps))
            yi = np.interp(xi, xlog, ylog, left=ylog[0], right=ylog[-1])
            return np.exp(yi)
        
        SA_x = safe_interp(curves_x.T, curves_x.Sa_p_g, T_grid)
        SA_y = safe_interp(curves_y.T, curves_y.Sa_p_g, T_grid)
        
        # SRSS hesapla
        SA_srss = calculate_srss_spectrum(SA_x, SA_y)
        srss_list.append(SA_srss)
    
    return srss_list


def scale_3d_simple_tbdy(
    records: Sequence[Tuple[np.ndarray, np.ndarray, float, Dict]],
    T1: float,
    SDS: float,
    SD1: float,
    TL: float = 6.0,
    T_grid: Optional[np.ndarray] = None,
    weights: Optional[np.ndarray] = None,
    alpha: float = 1.3,
    damping: float = 5.0
) -> TBDYScaleResult:
    """
    TBDY-2018 uyumlu 3B basit ölçeklendirme.
    
    Algoritma (belgeye uygun):
    1. Kayıt validasyonu (≥11, aynı olay ≤3)
    2. Her kayıt için SRSS spektrumu hesapla
    3. PEER kapalı form ile kayıt bazlı ölçek katsayıları
    4. Ortalama spektrum hesapla
    5. 1.30 koşulu kontrolü ve global gamma düzeltmesi
    
    Args:
        records: Kayıt listesi [(ax, ay, dt, meta), ...]
        T1: Birinci doğal periyot
        SDS: Kısa periyot tasarım spektral ivme katsayısı
        SD1: 1 saniyelik tasarım spektral ivme katsayısı
        TL: Geçiş periyodu
        T_grid: Periyot ızgarası (varsayılan: 301 nokta)
        weights: Ağırlık fonksiyonu
        alpha: TBDY çarpanı (3B için 1.30)
        damping: Sönüm oranı
        
    Returns:
        TBDYScaleResult: TBDY ölçeklendirme sonuçları
    """
    # 1. Validasyon
    is_valid, msg = validate_records_tbdy(records)
    if not is_valid:
        raise ValueError(f"Kayıt validasyonu başarısız: {msg}")
    
    # 2. Periyot ızgarası ve hedef spektrum
    if T_grid is None:
        T_grid = build_period_grid()
    
    if weights is None:
        weights = create_uniform_weights(T_grid)
    
    # Tasarım spektrumu
    S_design = design_spectrum_tbdy(T_grid, SDS, SD1, TL)
    target_spectrum = alpha * S_design
    
    # 3. SRSS spektrumları hesapla
    srss_list = compute_srss_spectra(records, T_grid, damping)
    
    # 4. Ağırlıkları normalize et (TBDY aralığı)
    weights_norm = normalize_weights_tbdy(weights, T_grid, T1)
    
    # 5. Kayıt bazlı ölçek katsayıları (PEER kapalı form)
    f_list = []
    mse_list = []
    
    for srss in srss_list:
        f = calculate_range_scale_factor(target_spectrum, srss, weights_norm)
        f_list.append(f)
        
        # MSE hesapla
        srss_scaled = f * srss
        mse = calculate_mse_log_space(target_spectrum, srss_scaled, weights_norm)
        mse_list.append(mse)
    
    # 6. Ölçeklenmiş spektrumlar
    srss_scaled_list = [f * srss for f, srss in zip(f_list, srss_list)]
    
    # 7. Ortalama spektrum
    srss_avg = np.mean(srss_scaled_list, axis=0)
    
    # 8. TBDY koşulu kontrolü [0.2×T1, 1.5×T1]
    T_min, T_max = 0.2 * T1, 1.5 * T1
    mask = (T_grid >= T_min) & (T_grid <= T_max)
    
    # Minimum oran hesapla
    ratios = srss_avg[mask] / target_spectrum[mask]
    min_ratio = float(np.min(ratios))
    pass_tbdy = min_ratio >= 1.0
    
    # 9. Global gamma düzeltmesi (gerekirse)
    global_gamma = 1.0
    gamma_applied = False
    
    if not pass_tbdy:
        # Global gamma = 1/min_ratio
        global_gamma = 1.0 / min_ratio
        gamma_applied = True
        
        # Tüm katsayıları uygula: base f_list'i KORU; applied listeyi ayrı tut
        applied_f_list = [global_gamma * f for f in f_list]
        srss_scaled_list = [af * srss for af, srss in zip(applied_f_list, srss_scaled_list)]
        srss_avg = global_gamma * srss_avg
        
        # Yeni minimum oran (≥1.0 olmalı)
        ratios_corrected = srss_avg[mask] / target_spectrum[mask]
        min_ratio = float(np.min(ratios_corrected))
        pass_tbdy = min_ratio >= 1.0
    else:
        applied_f_list = f_list[:]  # gamma 1.0
    
    # 10. Aynı olay kontrolü
    event_ids = set()
    for _, _, _, meta in records:
        event_id = meta.get("event_id") or meta.get("group_id")
        if event_id:
            event_ids.add(event_id)
    same_event_check = all(
        sum(1 for _, _, _, m in records 
            if m.get("event_id") == eid or m.get("group_id") == eid) <= 3 
        for eid in event_ids
    )
    
    return TBDYScaleResult(
        f_list=f_list,
        f_applied_list=applied_f_list,
        mse_list=mse_list,
        srss_scaled_list=srss_scaled_list,
        srss_avg=srss_avg,
        target_spectrum=target_spectrum,
        T_grid=T_grid,
        min_ratio=min_ratio,
        pass_tbdy=pass_tbdy,
        global_gamma=global_gamma,
        gamma_applied=gamma_applied,
        n_records=len(records),
        same_event_check=same_event_check,
        T1=T1,
        T_range=(T_min, T_max)
    )


def design_spectrum_tbdy(T: np.ndarray, SDS: float, SD1: float, TL: float = 6.0) -> np.ndarray:
    """
    TBDY-2018 tasarım spektrumu hesaplar.
    
    Args:
        T: Periyot dizisi
        SDS: Kısa periyot tasarım spektral ivme katsayısı
        SD1: 1 saniyelik tasarım spektral ivme katsayısı
        TL: Geçiş periyodu
        
    Returns:
        np.ndarray: Tasarım spektrumu Sa(T)
    """
    TA = 0.2 * SD1 / SDS if SDS > 0 else 0.0
    TB = SD1 / SDS if SDS > 0 else 0.0
    
    T = np.asarray(T, dtype=float)
    T_safe = np.where(T == 0.0, 1e-12, T)
    
    # Dört bölge
    Sa = np.zeros_like(T)
    
    # Bölge 1: T ≤ TA
    mask1 = T <= TA
    if TA > 0:
        Sa[mask1] = (0.4 + 0.6 * T[mask1] / TA) * SDS
    else:
        Sa[mask1] = 0.4 * SDS
    
    # Bölge 2: TA < T ≤ TB
    mask2 = (T > TA) & (T <= TB)
    Sa[mask2] = SDS
    
    # Bölge 3: TB < T ≤ TL
    mask3 = (T > TB) & (T <= TL)
    Sa[mask3] = SD1 / T_safe[mask3]
    
    # Bölge 4: T > TL
    mask4 = T > TL
    Sa[mask4] = SD1 * TL / (T_safe[mask4] ** 2)
    
    return np.maximum(Sa, 0.0)


def export_tbdy_results_csv(
    result: TBDYScaleResult,
    records_meta: List[Dict],
    filename: str = "tbdy_3d_scaling_results.csv"
) -> str:
    """
    TBDY sonuçlarını belirtilen CSV şemasına göre dışa aktarır.
    
    CSV şeması (belgeden):
    set_id | event | station | NGA_id | f | gamma | min_ratio | mse | pass_3D | notes
    
    Args:
        result: TBDY ölçeklendirme sonuçları
        records_meta: Kayıt meta verileri
        filename: Çıktı dosya adı
        
    Returns:
        str: Oluşturulan dosya yolu
    """
    import csv
    import os
    
    # CSV başlıkları
    headers = [
        "set_id", "event", "station", "NGA_id",
        "f", "gamma",
        "min_ratio", "mse", "pass_3D", "notes"
    ]
    
    # Verileri hazırla
    rows = []
    for i, (f_base, mse, meta) in enumerate(zip(result.f_list, result.mse_list, records_meta)):
        applied = (
            result.f_applied_list[i]
            if (getattr(result, "f_applied_list", None) and i < len(result.f_applied_list))
            else f_base
        )
        row = {
            "set_id": i + 1,
            "event": meta.get("event_id", f"Event_{i+1}"),
            "station": meta.get("station", f"Station_{i+1}"),
            "NGA_id": meta.get("nga_number", f"NGA_{i+1:04d}"),
            "f": f"{applied:.6f}",
            "gamma": f"{result.global_gamma:.6f}",
            "min_ratio": f"{result.min_ratio:.6f}",
            "mse": f"{mse:.6f}",
            "pass_3D": "PASS" if result.pass_tbdy else "FAIL",
            "notes": ("Global gamma uygulandı"
                      if result.gamma_applied
                      else "Normal ölçekleme")
        }
        rows.append(row)
    
    # CSV'ye yaz
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    
    return os.path.abspath(filename)


# Test fonksiyonu
if __name__ == "__main__":
    # Test verisi oluştur
    np.random.seed(42)
    
    # 12 kayıt (3 farklı olay)
    records = []
    records_meta = []
    
    for event_id in range(3):
        for record_id in range(4):
            # Rastgele zaman serisi (10 sn, 0.01 dt)
            dt = 0.01
            t = np.arange(0, 10, dt)
            ax = np.random.normal(0, 0.1, len(t)) * np.exp(-t/5)  # Azalan rastgele
            ay = np.random.normal(0, 0.1, len(t)) * np.exp(-t/5)
            
            meta = {
                "event_id": f"Event_{event_id+1}",
                "station": f"Station_{record_id+1}",
                "nga_number": f"NGA_{event_id*4 + record_id + 1:04d}"
            }
            
            records.append((ax, ay, dt, meta))
            records_meta.append(meta)
    
    # TBDY parametreleri
    T1 = 1.0
    SDS = 0.8
    SD1 = 0.6
    TL = 6.0
    
    print("TBDY-2018 3B Basit Ölçeklendirme Testi")
    print("=" * 50)
    
    try:
        # TBDY ölçeklendirme
        result = scale_3d_simple_tbdy(records, T1, SDS, SD1, TL)
        
        print(f"Kayıt sayısı: {result.n_records}")
        print(f"T1: {result.T1} s")
        print(f"Kontrol aralığı: [{result.T_range[0]:.3f}, {result.T_range[1]:.3f}] s")
        print(f"Minimum oran: {result.min_ratio:.6f}")
        print(f"TBDY koşulu: {'GEÇTİ' if result.pass_tbdy else 'KALDI'}")
        print(f"Global gamma: {result.global_gamma:.6f}")
        print(f"Gamma uygulandı: {'Evet' if result.gamma_applied else 'Hayır'}")
        print(f"Aynı olay kontrolü: {'GEÇTİ' if result.same_event_check else 'KALDI'}")
        
        print(f"\nÖlçek katsayıları:")
        for i, (f, mse) in enumerate(zip(result.f_list[:5], result.mse_list[:5])):
            print(f"  Kayıt {i+1}: f={f:.6f}, MSE={mse:.6f}")
        if len(result.f_list) > 5:
            print(f"  ... ve {len(result.f_list)-5} kayıt daha")
        
        # CSV dışa aktarma
        csv_file = export_tbdy_results_csv(result, records_meta, "test_tbdy_results.csv")
        print(f"\nSonuçlar CSV'ye aktarıldı: {csv_file}")
        
    except Exception as e:
        print(f"Hata: {e}")
