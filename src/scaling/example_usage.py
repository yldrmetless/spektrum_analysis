"""
3B Ölçekleme Örnek Kullanım
==========================

PGMD uyumlu 3B ölçekleme modüllerinin nasıl kullanılacağını gösteren örnek.
"""

import numpy as np
from typing import List, Dict, Any
from .scaling_3d_main import Scaling3DProcessor, Scaling3DConfig, create_default_config
from .ranking_selection import RecordMetadata


def create_sample_data():
    """Örnek veri oluşturur."""
    from .period_grid import build_period_grid
    
    # Periyot ızgarası
    T = build_period_grid()
    
    # Hedef spektrum (TBDY benzeri)
    target_spectrum = np.zeros_like(T)
    for i, t in enumerate(T):
        if t <= 0.1:
            target_spectrum[i] = 0.4 * (1 + 3 * t)
        elif t <= 1.0:
            target_spectrum[i] = 0.4
        else:
            target_spectrum[i] = 0.4 / t
    
    # Örnek kayıtlar
    n_records = 5
    records_data = []
    metadata = []
    
    for i in range(n_records):
        # Sahte spektral ivme verileri
        SA_FN = 0.2 * (1 + 0.1 * i) * np.ones_like(T)
        SA_FP = 0.25 * (1 + 0.1 * i) * np.ones_like(T)
        SA_V = 0.22 * (1 + 0.1 * i) * np.ones_like(T)
        
        record_data = {
            "SA_FN": SA_FN,
            "SA_FP": SA_FP,
            "SA_V": SA_V
        }
        records_data.append(record_data)
        
        # Meta veri
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
            pgd=0.01 + i * 0.005,
            file_names={
                "FN": f"record_{i+1}_FN.txt",
                "FP": f"record_{i+1}_FP.txt",
                "V": f"record_{i+1}_V.txt"
            }
        )
        metadata.append(meta)
    
    return T, target_spectrum, records_data, metadata


def example_basic_scaling():
    """Temel 3B ölçekleme örneği."""
    print("=== Temel 3B Ölçekleme Örneği ===")
    
    # Veri oluştur
    T, target_spectrum, records_data, metadata = create_sample_data()
    
    # Varsayılan konfigürasyon
    config = create_default_config()
    processor = Scaling3DProcessor(config)
    
    # Hedef spektrumu ayarla
    processor.set_target_spectrum(target_spectrum)
    
    # Kayıtları işle
    processor.process_records(records_data, metadata)
    
    # Yönetmelik kontrollerini yap
    processor.perform_regulatory_checks(T_design=1.0)
    
    # Sonuçları göster
    print(f"İşlenen kayıt sayısı: {len(processor.results)}")
    
    for i, result in enumerate(processor.results):
        print(f"Kayıt {i+1}: f={result.f:.6f}, MSE={result.mse:.6f}")
    
    # İstatistikler
    stats = processor.get_statistics()
    print(f"\nİstatistikler:")
    print(f"MSE: {stats.get('mse_mean', 0):.6f} ± {stats.get('mse_std', 0):.6f}")
    print(f"Ölçek katsayısı: {stats.get('f_mean', 0):.6f} ± {stats.get('f_std', 0):.6f}")
    print(f"Pulse oranı: {stats.get('pulse_ratio', 0):.1%}")
    
    # Yönetmelik kontrolleri
    print(f"\nYönetmelik kontrolleri:")
    for check_name, check_result in processor.regulatory_checks.items():
        status = "✓" if check_result.passed else "✗"
        print(f"{status} {check_name}: {check_result.message}")


def example_custom_weights():
    """Özel ağırlık fonksiyonu örneği."""
    print("\n=== Özel Ağırlık Fonksiyonu Örneği ===")
    
    # Veri oluştur
    T, target_spectrum, records_data, metadata = create_sample_data()
    
    # Özel konfigürasyon
    config = Scaling3DConfig(
        mode="range",
        weight_type="custom",
        weight_params={
            "period_knots": np.array([0.1, 0.5, 1.0, 2.0, 5.0]),
            "weight_knots": np.array([1.0, 2.0, 3.0, 2.0, 1.0])
        },
        n_top_records=3
    )
    
    processor = Scaling3DProcessor(config)
    processor.set_target_spectrum(target_spectrum)
    processor.process_records(records_data, metadata)
    
    print(f"Özel ağırlık fonksiyonu ile işlenen kayıt sayısı: {len(processor.results)}")
    
    # En iyi 3 kayıt
    top_results, top_metadata, top_indices = processor.select_top_records()
    print(f"En iyi 3 kayıt:")
    for i, (result, meta) in enumerate(zip(top_results, top_metadata)):
        print(f"  {i+1}. NGA{meta.nga_number}: f={result.f:.6f}, MSE={result.mse:.6f}")


def example_filtering():
    """Filtreleme örneği."""
    print("\n=== Filtreleme Örneği ===")
    
    # Veri oluştur
    T, target_spectrum, records_data, metadata = create_sample_data()
    
    # Filtreleme kriterleri
    filter_criteria = {
        "max_mse": 0.5,
        "min_scale_factor": 0.3,
        "max_scale_factor": 3.0,
        "pulse_only": False
    }
    
    config = Scaling3DConfig(
        mode="range",
        weight_type="uniform",
        filter_criteria=filter_criteria
    )
    
    processor = Scaling3DProcessor(config)
    processor.set_target_spectrum(target_spectrum)
    processor.process_records(records_data, metadata)
    
    print(f"Filtreleme sonrası kayıt sayısı: {len(processor.results)}")
    
    # Filtrelenmiş sonuçlar
    for i, result in enumerate(processor.results):
        print(f"Kayıt {i+1}: f={result.f:.6f}, MSE={result.mse:.6f}")


def example_export():
    """Dışa aktarma örneği."""
    print("\n=== Dışa Aktarma Örneği ===")
    
    # Veri oluştur
    T, target_spectrum, records_data, metadata = create_sample_data()
    
    config = Scaling3DConfig(
        mode="range",
        weight_type="uniform",
        output_dir="test_output",
        export_formats=["json", "csv", "txt"]
    )
    
    processor = Scaling3DProcessor(config)
    processor.set_target_spectrum(target_spectrum)
    processor.process_records(records_data, metadata)
    processor.perform_regulatory_checks(T_design=1.0)
    
    # Dışa aktarma
    try:
        files_created = processor.export_results(T_design=1.0, prefix="example")
        print(f"Dışa aktarma başarılı:")
        for file_type, file_path in files_created.items():
            print(f"  {file_type}: {file_path}")
    except Exception as e:
        print(f"Dışa aktarma hatası: {e}")


def example_advanced():
    """Gelişmiş örnek."""
    print("\n=== Gelişmiş Örnek ===")
    
    # Veri oluştur
    T, target_spectrum, records_data, metadata = create_sample_data()
    
    # Gelişmiş konfigürasyon
    config = Scaling3DConfig(
        mode="range",
        weight_type="band",
        weight_params={
            "T_center": 1.0,
            "bandwidth": 0.5,
            "shape": "gaussian"
        },
        scale_limits=(0.2, 5.0),
        filter_criteria={
            "max_mse": 1.0,
            "min_scale_factor": 0.1,
            "max_scale_factor": 10.0
        },
        regulatory_checks={
            "asce_7_16": {"threshold_ratio": 0.9, "band_range": (0.2, 2.0)},
            "tbdy": {"threshold_ratio": 0.9, "band_range": (0.2, 1.5)},
            "spectral_shape": {"shape_tolerance": 0.1}
        },
        n_top_records=3,
        output_dir="advanced_output"
    )
    
    processor = Scaling3DProcessor(config)
    processor.set_target_spectrum(target_spectrum)
    processor.process_records(records_data, metadata)
    processor.perform_regulatory_checks(T_design=1.0)
    
    # Sonuçları göster
    print(f"Gelişmiş işlem sonucu:")
    print(f"İşlenen kayıt sayısı: {len(processor.results)}")
    
    # En iyi kayıtlar
    top_results, top_metadata, top_indices = processor.select_top_records()
    print(f"\nEn iyi {len(top_results)} kayıt:")
    for i, (result, meta) in enumerate(zip(top_results, top_metadata)):
        print(f"  {i+1}. NGA{meta.nga_number}: f={result.f:.6f}, MSE={result.mse:.6f}")
    
    # Yönetmelik kontrolleri
    print(f"\nYönetmelik kontrolleri:")
    for check_name, check_result in processor.regulatory_checks.items():
        status = "✓" if check_result.passed else "✗"
        print(f"{status} {check_name}: {check_result.message}")
    
    # Suite ortalamaları
    suite_stats = processor.get_suite_averages(component="GM")
    print(f"\nSuite ortalamaları:")
    print(f"Kayıt sayısı: {suite_stats.get('n_records', 0)}")
    print(f"Ortalama MSE: {suite_stats.get('mse_mean', 0):.6f}")
    print(f"Ortalama f: {suite_stats.get('f_mean', 0):.6f}")


if __name__ == "__main__":
    # Tüm örnekleri çalıştır
    example_basic_scaling()
    example_custom_weights()
    example_filtering()
    example_export()
    example_advanced()
    
    print("\n=== Tüm örnekler tamamlandı ===")
