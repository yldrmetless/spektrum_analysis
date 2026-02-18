"""
3B Ölçekleme için Kayıt Sıralama ve Seçim Modülü
===============================================

MSE tabanlı kayıt sıralama, seçim ve filtreleme işlemleri.
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any, Callable
from dataclasses import dataclass
from .scale_3d import ScaleResult3D


@dataclass
class RecordMetadata:
    """Kayıt meta verileri."""
    nga_number: Optional[str] = None
    pulse: bool = False
    pulse_period: Optional[float] = None
    duration_5_95: Optional[float] = None
    r_rup: Optional[float] = None
    r_jb: Optional[float] = None
    vs30: Optional[float] = None
    lowest_usable_freq: Optional[float] = None
    pga: Optional[float] = None
    pgv: Optional[float] = None
    pgd: Optional[float] = None
    file_names: Optional[Dict[str, str]] = None


@dataclass
class RankingResult:
    """Sıralama sonuçları."""
    ranked_indices: List[int]
    ranked_results: List[ScaleResult3D]
    metadata: List[RecordMetadata]
    mse_values: List[float]
    scale_factors: List[float]


def rank_records_by_mse(
    results: List[ScaleResult3D],
    metadata: Optional[List[RecordMetadata]] = None
) -> RankingResult:
    """
    Kayıtları MSE'ye göre sıralar.
    
    Args:
        results: Ölçekleme sonuçları listesi
        metadata: Kayıt meta verileri (opsiyonel)
        
    Returns:
        RankingResult: Sıralama sonuçları
    """
    if not results:
        return RankingResult([], [], [], [], [])
    
    # MSE'ye göre sırala
    n_records = len(results)
    mse_values = [r.mse for r in results]
    scale_factors = [r.f for r in results]
    
    # Sıralama indeksleri
    ranked_indices = sorted(range(n_records), key=lambda i: mse_values[i])
    
    # Sıralanmış sonuçlar
    ranked_results = [results[i] for i in ranked_indices]
    
    # Sıralanmış meta veriler
    if metadata is not None:
        ranked_metadata = [metadata[i] for i in ranked_indices]
    else:
        ranked_metadata = [RecordMetadata() for _ in range(n_records)]
    
    # Sıralanmış MSE ve ölçek katsayıları
    ranked_mse = [mse_values[i] for i in ranked_indices]
    ranked_f = [scale_factors[i] for i in ranked_indices]
    
    return RankingResult(
        ranked_indices=ranked_indices,
        ranked_results=ranked_results,
        metadata=ranked_metadata,
        mse_values=ranked_mse,
        scale_factors=ranked_f
    )


def filter_records_by_criteria(
    results: List[ScaleResult3D],
    metadata: List[RecordMetadata],
    criteria: Dict[str, Any]
) -> Tuple[List[int], List[ScaleResult3D], List[RecordMetadata]]:
    """
    Kayıtları belirli kriterlere göre filtreler.
    
    Args:
        results: Ölçekleme sonuçları listesi
        metadata: Kayıt meta verileri
        criteria: Filtreleme kriterleri
        
    Returns:
        Tuple[List[int], List[ScaleResult3D], List[RecordMetadata]]: Filtrelenmiş veriler
    """
    if not results:
        return [], [], []
    
    n_records = len(results)
    valid_indices = []
    
    for i in range(n_records):
        valid = True
        meta = metadata[i]
        
        # MSE sınırı
        if "max_mse" in criteria:
            if results[i].mse > criteria["max_mse"]:
                valid = False
        
        # Ölçek katsayısı sınırları
        if "min_scale_factor" in criteria:
            if results[i].f < criteria["min_scale_factor"]:
                valid = False
        
        if "max_scale_factor" in criteria:
            if results[i].f > criteria["max_scale_factor"]:
                valid = False
        
        # LUF kontrolü
        if "min_luf" in criteria and meta.lowest_usable_freq is not None:
            if meta.lowest_usable_freq > criteria["min_luf"]:
                valid = False
        
        # Mesafe sınırları
        if "max_r_rup" in criteria and meta.r_rup is not None:
            if meta.r_rup > criteria["max_r_rup"]:
                valid = False
        
        if "max_r_jb" in criteria and meta.r_jb is not None:
            if meta.r_jb > criteria["max_r_jb"]:
                valid = False
        
        # VS30 sınırları
        if "min_vs30" in criteria and meta.vs30 is not None:
            if meta.vs30 < criteria["min_vs30"]:
                valid = False
        
        if "max_vs30" in criteria and meta.vs30 is not None:
            if meta.vs30 > criteria["max_vs30"]:
                valid = False
        
        # Pulse filtresi
        if "pulse_only" in criteria and criteria["pulse_only"]:
            if not meta.pulse:
                valid = False
        
        if "no_pulse" in criteria and criteria["no_pulse"]:
            if meta.pulse:
                valid = False
        
        # Süre sınırları
        if "min_duration" in criteria and meta.duration_5_95 is not None:
            if meta.duration_5_95 < criteria["min_duration"]:
                valid = False
        
        if "max_duration" in criteria and meta.duration_5_95 is not None:
            if meta.duration_5_95 > criteria["max_duration"]:
                valid = False
        
        if valid:
            valid_indices.append(i)
    
    # Filtrelenmiş veriler
    filtered_results = [results[i] for i in valid_indices]
    filtered_metadata = [metadata[i] for i in valid_indices]
    
    return valid_indices, filtered_results, filtered_metadata


def select_top_records(
    results: List[ScaleResult3D],
    metadata: Optional[List[RecordMetadata]] = None,
    n_top: int = 10,
    criteria: Optional[Dict[str, Any]] = None
) -> Tuple[List[ScaleResult3D], List[RecordMetadata], List[int]]:
    """
    En iyi N kaydı seçer.
    
    Args:
        results: Ölçekleme sonuçları listesi
        metadata: Kayıt meta verileri
        n_top: Seçilecek kayıt sayısı
        criteria: Filtreleme kriterleri
        
    Returns:
        Tuple[List[ScaleResult3D], List[RecordMetadata], List[int]]: Seçilen kayıtlar
    """
    if not results:
        return [], [], []
    
    # Varsayılan meta veriler
    if metadata is None:
        metadata = [RecordMetadata() for _ in range(len(results))]
    
    # Filtreleme uygula
    if criteria is not None:
        valid_indices, filtered_results, filtered_metadata = filter_records_by_criteria(
            results, metadata, criteria
        )
    else:
        filtered_results = results
        filtered_metadata = metadata
        valid_indices = list(range(len(results)))
    
    # MSE'ye göre sırala
    ranking = rank_records_by_mse(filtered_results, filtered_metadata)
    
    # En iyi N kaydı seç
    n_select = min(n_top, len(ranking.ranked_results))
    selected_results = ranking.ranked_results[:n_select]
    selected_metadata = ranking.ranked_metadata[:n_select]
    selected_indices = [valid_indices[ranking.ranked_indices[i]] for i in range(n_select)]
    
    return selected_results, selected_metadata, selected_indices


def calculate_selection_statistics(
    results: List[ScaleResult3D],
    metadata: List[RecordMetadata]
) -> Dict[str, Any]:
    """
    Seçim istatistiklerini hesaplar.
    
    Args:
        results: Ölçekleme sonuçları listesi
        metadata: Kayıt meta verileri
        
    Returns:
        Dict[str, Any]: Seçim istatistikleri
    """
    if not results:
        return {}
    
    n_records = len(results)
    
    # MSE istatistikleri
    mse_values = [r.mse for r in results]
    mse_mean = np.mean(mse_values)
    mse_std = np.std(mse_values)
    mse_min = np.min(mse_values)
    mse_max = np.max(mse_values)
    
    # Ölçek katsayısı istatistikleri
    f_values = [r.f for r in results]
    f_mean = np.mean(f_values)
    f_std = np.std(f_values)
    f_min = np.min(f_values)
    f_max = np.max(f_values)
    
    # Meta veri istatistikleri
    pulse_count = sum(1 for meta in metadata if meta.pulse)
    pulse_ratio = pulse_count / n_records if n_records > 0 else 0
    
    # Mesafe istatistikleri
    r_rup_values = [meta.r_rup for meta in metadata if meta.r_rup is not None]
    r_jb_values = [meta.r_jb for meta in metadata if meta.r_jb is not None]
    vs30_values = [meta.vs30 for meta in metadata if meta.vs30 is not None]
    
    # Süre istatistikleri
    duration_values = [meta.duration_5_95 for meta in metadata if meta.duration_5_95 is not None]
    
    # LUF istatistikleri
    luf_values = [meta.lowest_usable_freq for meta in metadata if meta.lowest_usable_freq is not None]
    
    stats = {
        "n_records": n_records,
        "mse_mean": mse_mean,
        "mse_std": mse_std,
        "mse_min": mse_min,
        "mse_max": mse_max,
        "f_mean": f_mean,
        "f_std": f_std,
        "f_min": f_min,
        "f_max": f_max,
        "pulse_count": pulse_count,
        "pulse_ratio": pulse_ratio
    }
    
    if r_rup_values:
        stats["r_rup_mean"] = np.mean(r_rup_values)
        stats["r_rup_std"] = np.std(r_rup_values)
        stats["r_rup_min"] = np.min(r_rup_values)
        stats["r_rup_max"] = np.max(r_rup_values)
    
    if r_jb_values:
        stats["r_jb_mean"] = np.mean(r_jb_values)
        stats["r_jb_std"] = np.std(r_jb_values)
        stats["r_jb_min"] = np.min(r_jb_values)
        stats["r_jb_max"] = np.max(r_jb_values)
    
    if vs30_values:
        stats["vs30_mean"] = np.mean(vs30_values)
        stats["vs30_std"] = np.std(vs30_values)
        stats["vs30_min"] = np.min(vs30_values)
        stats["vs30_max"] = np.max(vs30_values)
    
    if duration_values:
        stats["duration_mean"] = np.mean(duration_values)
        stats["duration_std"] = np.std(duration_values)
        stats["duration_min"] = np.min(duration_values)
        stats["duration_max"] = np.max(duration_values)
    
    if luf_values:
        stats["luf_mean"] = np.mean(luf_values)
        stats["luf_std"] = np.std(luf_values)
        stats["luf_min"] = np.min(luf_values)
        stats["luf_max"] = np.max(luf_values)
    
    return stats


def create_default_criteria() -> Dict[str, Any]:
    """
    Varsayılan filtreleme kriterlerini oluşturur.
    
    Returns:
        Dict[str, Any]: Varsayılan kriterler
    """
    return {
        "max_mse": 1.0,           # Maksimum MSE
        "min_scale_factor": 0.1,   # Minimum ölçek katsayısı
        "max_scale_factor": 10.0,  # Maksimum ölçek katsayısı
        "max_r_rup": 200.0,        # Maksimum Rrup (km)
        "max_r_jb": 200.0,         # Maksimum Rjb (km)
        "min_vs30": 100.0,         # Minimum VS30 (m/s)
        "max_vs30": 2000.0,        # Maksimum VS30 (m/s)
        "min_luf": 0.1,            # Minimum LUF (Hz)
        "min_duration": 5.0,       # Minimum süre (s)
        "max_duration": 120.0       # Maksimum süre (s)
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
    metadata = []
    
    for i in range(n_records):
        # Sahte ölçekleme sonucu
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
        
        # Sahte meta veri
        meta = RecordMetadata(
            nga_number=f"NGA{i+1:04d}",
            pulse=i % 2 == 0,
            pulse_period=0.5 + i * 0.1 if i % 2 == 0 else None,
            duration_5_95=10.0 + i * 5.0,
            r_rup=10.0 + i * 20.0,
            r_jb=8.0 + i * 18.0,
            vs30=200.0 + i * 100.0,
            lowest_usable_freq=0.1 + i * 0.05,
            pga=0.1 + i * 0.05,
            pgv=0.05 + i * 0.02,
            pgd=0.01 + i * 0.005
        )
        metadata.append(meta)
    
    # Test 1: Sıralama
    ranking = rank_records_by_mse(results, metadata)
    print("MSE sıralaması:")
    for i, (idx, result) in enumerate(zip(ranking.ranked_indices, ranking.ranked_results)):
        print(f"Sıra {i+1}: Kayıt {idx+1}, MSE={result.mse:.6f}, f={result.f:.6f}")
    
    # Test 2: Filtreleme
    criteria = {
        "max_mse": 0.3,
        "min_scale_factor": 0.3,
        "max_scale_factor": 2.0,
        "pulse_only": False
    }
    
    valid_indices, filtered_results, filtered_metadata = filter_records_by_criteria(
        results, metadata, criteria
    )
    print(f"\nFiltreleme sonucu: {len(filtered_results)}/{len(results)} kayıt geçti")
    
    # Test 3: En iyi kayıtlar
    selected_results, selected_metadata, selected_indices = select_top_records(
        results, metadata, n_top=3, criteria=criteria
    )
    print(f"\nEn iyi 3 kayıt:")
    for i, (result, meta) in enumerate(zip(selected_results, selected_metadata)):
        print(f"Kayıt {i+1}: MSE={result.mse:.6f}, f={result.f:.6f}, NGA={meta.nga_number}")
    
    # Test 4: İstatistikler
    stats = calculate_selection_statistics(results, metadata)
    print(f"\nSeçim istatistikleri:")
    print(f"Kayıt sayısı: {stats['n_records']}")
    print(f"MSE: {stats['mse_mean']:.6f} ± {stats['mse_std']:.6f}")
    print(f"Ölçek katsayısı: {stats['f_mean']:.6f} ± {stats['f_std']:.6f}")
    print(f"Pulse oranı: {stats['pulse_ratio']:.2%}")
    
    # Test 5: Varsayılan kriterler
    default_criteria = create_default_criteria()
    print(f"\nVarsayılan kriterler: {default_criteria}")
