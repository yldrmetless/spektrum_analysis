"""
3B Ölçekleme için Raporlama ve Dışa Aktarma Modülü
================================================

3B ölçekleme sonuçları için CSV/JSON raporlama ve dışa aktarma.
"""

import numpy as np
import pandas as pd
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from .scale_3d import ScaleResult3D
from .ranking_selection import RecordMetadata, RankingResult
from .regulatory_checks import RegulatoryCheckResult


def create_scaling_report(
    results: List[ScaleResult3D],
    metadata: List[RecordMetadata],
    ranking: RankingResult,
    regulatory_checks: Dict[str, RegulatoryCheckResult],
    target_spectrum: np.ndarray,
    T_grid: np.ndarray,
    scaling_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    3B ölçekleme raporu oluşturur.
    
    Args:
        results: Ölçekleme sonuçları listesi
        metadata: Kayıt meta verileri
        ranking: Sıralama sonuçları
        regulatory_checks: Yönetmelik kontrol sonuçları
        target_spectrum: Hedef spektrum
        T_grid: Periyot ızgarası
        scaling_params: Ölçekleme parametreleri
        
    Returns:
        Dict[str, Any]: Rapor verisi
    """
    # Temel bilgiler
    report = {
        "timestamp": datetime.now().isoformat(),
        "n_records": len(results),
        "scaling_params": scaling_params,
        "T_grid": T_grid.tolist(),
        "target_spectrum": target_spectrum.tolist()
    }
    
    # Kayıt bazlı sonuçlar
    record_results = []
    for i, (result, meta) in enumerate(zip(results, metadata)):
        record_data = {
            "record_index": i,
            "nga_number": meta.nga_number,
            "scale_factor": result.f,
            "mse": result.mse,
            "pulse": meta.pulse,
            "pulse_period": meta.pulse_period,
            "duration_5_95": meta.duration_5_95,
            "r_rup": meta.r_rup,
            "r_jb": meta.r_jb,
            "vs30": meta.vs30,
            "lowest_usable_freq": meta.lowest_usable_freq,
            "pga": meta.pga,
            "pgv": meta.pgv,
            "pgd": meta.pgd,
            "file_names": meta.file_names,
            "SA_FN_scaled": result.SA_FN_scaled.tolist(),
            "SA_FP_scaled": result.SA_FP_scaled.tolist(),
            "SA_V_scaled": result.SA_V_scaled.tolist() if result.SA_V_scaled is not None else None,
            "SA_GM": result.SA_GM.tolist()
        }
        record_results.append(record_data)
    
    report["record_results"] = record_results
    
    # Sıralama bilgileri
    report["ranking"] = {
        "ranked_indices": ranking.ranked_indices,
        "mse_values": ranking.mse_values,
        "scale_factors": ranking.scale_factors
    }
    
    # Yönetmelik kontrol sonuçları
    regulatory_results = {}
    for check_name, check_result in regulatory_checks.items():
        regulatory_results[check_name] = {
            "passed": check_result.passed,
            "message": check_result.message,
            "details": check_result.details
        }
    report["regulatory_checks"] = regulatory_results
    
    # İstatistikler
    if results:
        mse_values = [r.mse for r in results]
        f_values = [r.f for r in results]
        
        stats = {
            "mse_mean": np.mean(mse_values),
            "mse_std": np.std(mse_values),
            "mse_min": np.min(mse_values),
            "mse_max": np.max(mse_values),
            "f_mean": np.mean(f_values),
            "f_std": np.std(f_values),
            "f_min": np.min(f_values),
            "f_max": np.max(f_values)
        }
        report["statistics"] = stats
    
    return report


def export_to_csv(
    results: List[ScaleResult3D],
    metadata: List[RecordMetadata],
    ranking: RankingResult,
    output_path: str,
    include_spectra: bool = True
) -> None:
    """
    Sonuçları CSV formatında dışa aktarır.
    
    Args:
        results: Ölçekleme sonuçları listesi
        metadata: Kayıt meta verileri
        ranking: Sıralama sonuçları
        output_path: Çıktı dosya yolu
        include_spectra: Spektral dizileri dahil et
    """
    # Temel veri tablosu
    data = []
    for i, (result, meta) in enumerate(zip(results, metadata)):
        row = {
            "Record_Index": i,
            "NGA_Number": meta.nga_number,
            "Scale_Factor": result.f,
            "MSE": result.mse,
            "Pulse": meta.pulse,
            "Pulse_Period": meta.pulse_period,
            "Duration_5_95": meta.duration_5_95,
            "R_rup": meta.r_rup,
            "R_jb": meta.r_jb,
            "VS30": meta.vs30,
            "Lowest_Usable_Freq": meta.lowest_usable_freq,
            "PGA": meta.pga,
            "PGV": meta.pgv,
            "PGD": meta.pgd
        }
        
        # Dosya adları
        if meta.file_names:
            for comp, filename in meta.file_names.items():
                row[f"File_{comp}"] = filename
        
        # Spektral diziler (opsiyonel)
        if include_spectra:
            row["SA_FN_scaled"] = json.dumps(result.SA_FN_scaled.tolist())
            row["SA_FP_scaled"] = json.dumps(result.SA_FP_scaled.tolist())
            if result.SA_V_scaled is not None:
                row["SA_V_scaled"] = json.dumps(result.SA_V_scaled.tolist())
            row["SA_GM"] = json.dumps(result.SA_GM.tolist())
        
        data.append(row)
    
    # DataFrame oluştur ve kaydet
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False, encoding='utf-8')


def export_to_json(
    report_data: Dict[str, Any],
    output_path: str
) -> None:
    """
    Rapor verisini JSON formatında dışa aktarır.
    
    Args:
        report_data: Rapor verisi
        output_path: Çıktı dosya yolu
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)


def export_spectra_to_csv(
    results: List[ScaleResult3D],
    T_grid: np.ndarray,
    output_path: str,
    component: str = "GM"
) -> None:
    """
    Spektral dizileri CSV formatında dışa aktarır.
    
    Args:
        results: Ölçekleme sonuçları listesi
        T_grid: Periyot ızgarası
        output_path: Çıktı dosya yolu
        component: Bileşen ("FN", "FP", "V", "GM")
    """
    # Bileşen seçimi
    if component == "FN":
        spectra = [r.SA_FN_scaled for r in results]
    elif component == "FP":
        spectra = [r.SA_FP_scaled for r in results]
    elif component == "V":
        spectra = [r.SA_V_scaled for r in results if r.SA_V_scaled is not None]
    elif component == "GM":
        spectra = [r.SA_GM for r in results]
    else:
        raise ValueError(f"Bilinmeyen bileşen: {component}")
    
    if not spectra:
        raise ValueError(f"{component} bileşeni için spektrum verisi yok")
    
    # Spektral dizileri DataFrame'e dönüştür
    data = {"Period": T_grid}
    for i, spectrum in enumerate(spectra):
        data[f"Record_{i+1}"] = spectrum
    
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False, encoding='utf-8')


def export_suite_averages_to_csv(
    suite_average: Dict[str, Any],
    T_grid: np.ndarray,
    output_path: str
) -> None:
    """
    Suite ortalamalarını CSV formatında dışa aktarır.
    
    Args:
        suite_average: Suite ortalaması sonuçları
        T_grid: Periyot ızgarası
        output_path: Çıktı dosya yolu
    """
    data = {
        "Period": T_grid,
        "Arithmetic_Mean": suite_average["arithmetic_mean"],
        "Geometric_Mean": suite_average["geometric_mean"],
        "Std_Dev": suite_average["std_dev"],
        "CV": suite_average["cv"]
    }
    
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False, encoding='utf-8')


def create_summary_report(
    results: List[ScaleResult3D],
    metadata: List[RecordMetadata],
    regulatory_checks: Dict[str, RegulatoryCheckResult],
    scaling_params: Dict[str, Any]
) -> str:
    """
    Özet rapor metni oluşturur.
    
    Args:
        results: Ölçekleme sonuçları listesi
        metadata: Kayıt meta verileri
        regulatory_checks: Yönetmelik kontrol sonuçları
        scaling_params: Ölçekleme parametreleri
        
    Returns:
        str: Özet rapor metni
    """
    n_records = len(results)
    
    # Temel istatistikler
    mse_values = [r.mse for r in results]
    f_values = [r.f for r in results]
    
    mse_mean = np.mean(mse_values)
    mse_std = np.std(mse_values)
    f_mean = np.mean(f_values)
    f_std = np.std(f_values)
    
    # Pulse istatistikleri
    pulse_count = sum(1 for meta in metadata if meta.pulse)
    pulse_ratio = pulse_count / n_records if n_records > 0 else 0
    
    # Yönetmelik kontrol sonuçları
    regulatory_summary = []
    for check_name, check_result in regulatory_checks.items():
        status = "✓" if check_result.passed else "✗"
        regulatory_summary.append(f"{status} {check_name}: {check_result.message}")
    
    # Rapor metni
    report_text = f"""
3B ÖLÇEKLEME RAPORU
==================

Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

GENEL BİLGİLER
--------------
• Toplam kayıt sayısı: {n_records}
• Ölçekleme modu: {scaling_params.get('mode', 'N/A')}
• Ağırlık fonksiyonu: {scaling_params.get('weight_type', 'N/A')}

İSTATİSTİKLER
-------------
• MSE: {mse_mean:.6f} ± {mse_std:.6f}
• Ölçek katsayısı: {f_mean:.6f} ± {f_std:.6f}
• Pulse oranı: {pulse_ratio:.1%} ({pulse_count}/{n_records})

YÖNETMELİK KONTROLLERİ
---------------------
{chr(10).join(regulatory_summary)}

ÖLÇEKLEME PARAMETRELERİ
-----------------------
"""
    
    for key, value in scaling_params.items():
        report_text += f"• {key}: {value}\n"
    
    return report_text


def export_comprehensive_report(
    results: List[ScaleResult3D],
    metadata: List[RecordMetadata],
    ranking: RankingResult,
    regulatory_checks: Dict[str, RegulatoryCheckResult],
    target_spectrum: np.ndarray,
    T_grid: np.ndarray,
    scaling_params: Dict[str, Any],
    output_dir: str,
    prefix: str = "scaling_3d"
) -> Dict[str, str]:
    """
    Kapsamlı rapor paketi oluşturur.
    
    Args:
        results: Ölçekleme sonuçları listesi
        metadata: Kayıt meta verileri
        ranking: Sıralama sonuçları
        regulatory_checks: Yönetmelik kontrol sonuçları
        target_spectrum: Hedef spektrum
        T_grid: Periyot ızgarası
        scaling_params: Ölçekleme parametreleri
        output_dir: Çıktı dizini
        prefix: Dosya öneki
        
    Returns:
        Dict[str, str]: Oluşturulan dosya yolları
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    files_created = {}
    
    # 1. Ana rapor (JSON)
    report_data = create_scaling_report(
        results, metadata, ranking, regulatory_checks,
        target_spectrum, T_grid, scaling_params
    )
    json_path = output_path / f"{prefix}_report_{timestamp}.json"
    export_to_json(report_data, str(json_path))
    files_created["json_report"] = str(json_path)
    
    # 2. Kayıt tablosu (CSV)
    csv_path = output_path / f"{prefix}_records_{timestamp}.csv"
    export_to_csv(results, metadata, ranking, str(csv_path))
    files_created["csv_records"] = str(csv_path)
    
    # 3. Spektral diziler (CSV)
    for component in ["FN", "FP", "V", "GM"]:
        try:
            spectra_path = output_path / f"{prefix}_spectra_{component}_{timestamp}.csv"
            export_spectra_to_csv(results, T_grid, str(spectra_path), component)
            files_created[f"spectra_{component}"] = str(spectra_path)
        except ValueError:
            # Bileşen verisi yoksa atla
            pass
    
    # 4. Özet rapor (TXT)
    summary_text = create_summary_report(
        results, metadata, regulatory_checks, scaling_params
    )
    summary_path = output_path / f"{prefix}_summary_{timestamp}.txt"
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    files_created["summary"] = str(summary_path)
    
    return files_created


# Test fonksiyonu
if __name__ == "__main__":
    from .scale_3d import ScaleResult3D
    from .period_grid import build_period_grid
    from .ranking_selection import RecordMetadata, RankingResult
    from .regulatory_checks import RegulatoryCheckResult
    
    # Test verisi oluştur
    T = build_period_grid()
    n_records = 3
    
    # Sahte sonuçlar
    results = []
    metadata = []
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
        
        meta = RecordMetadata(
            nga_number=f"NGA{i+1:04d}",
            pulse=i % 2 == 0,
            duration_5_95=10.0 + i * 5.0,
            r_rup=10.0 + i * 20.0,
            vs30=200.0 + i * 100.0
        )
        metadata.append(meta)
    
    # Sahte sıralama
    ranking = RankingResult(
        ranked_indices=list(range(n_records)),
        ranked_results=results,
        metadata=metadata,
        mse_values=[r.mse for r in results],
        scale_factors=[r.f for r in results]
    )
    
    # Sahte yönetmelik kontrolleri
    regulatory_checks = {
        "asce_7_16": RegulatoryCheckResult(True, "ASCE 7-16 uyumlu", {}),
        "tbdy": RegulatoryCheckResult(True, "TBDY uyumlu", {})
    }
    
    # Test parametreleri
    target_spectrum = 0.4 * np.ones_like(T)
    scaling_params = {
        "mode": "range",
        "weight_type": "uniform",
        "n_records": n_records
    }
    
    # Test 1: Ana rapor
    report_data = create_scaling_report(
        results, metadata, ranking, regulatory_checks,
        target_spectrum, T, scaling_params
    )
    print(f"Rapor oluşturuldu: {len(report_data)} anahtar")
    print(f"Kayıt sayısı: {report_data['n_records']}")
    
    # Test 2: CSV dışa aktarma
    try:
        export_to_csv(results, metadata, ranking, "test_records.csv")
        print("CSV dışa aktarma başarılı")
    except Exception as e:
        print(f"CSV dışa aktarma hatası: {e}")
    
    # Test 3: Özet rapor
    summary_text = create_summary_report(
        results, metadata, regulatory_checks, scaling_params
    )
    print(f"\nÖzet rapor uzunluğu: {len(summary_text)} karakter")
    
    # Test 4: Kapsamlı rapor
    try:
        files_created = export_comprehensive_report(
            results, metadata, ranking, regulatory_checks,
            target_spectrum, T, scaling_params, "test_output"
        )
        print(f"\nKapsamlı rapor oluşturuldu:")
        for file_type, file_path in files_created.items():
            print(f"  {file_type}: {file_path}")
    except Exception as e:
        print(f"Kapsamlı rapor hatası: {e}")
