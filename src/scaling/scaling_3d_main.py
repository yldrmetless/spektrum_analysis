"""
3B Ölçekleme Ana Modülü
=====================

PGMD uyumlu 3B ölçekleme işlemlerini koordine eden ana modül.
Tüm alt modülleri bir araya getirir.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Alt modüller
from .period_grid import build_period_grid, validate_period_grid
from .weight_function import create_weight_function, create_uniform_weights, validate_weight_function
from .scale_factor import calculate_scale_factor, calculate_scale_factor_3d
from .scale_3d import scale_record_3d, scale_multiple_records_3d, calculate_suite_statistics
from .ranking_selection import (
    rank_records_by_mse, select_top_records, filter_records_by_criteria,
    calculate_selection_statistics, create_default_criteria, RecordMetadata
)
from .regulatory_checks import (
    perform_comprehensive_regulatory_checks, calculate_suite_averages,
    create_default_checks
)
from .reporting import (
    create_scaling_report, export_comprehensive_report, create_summary_report
)


@dataclass
class Scaling3DConfig:
    """3B ölçekleme konfigürasyonu."""
    mode: str = "range"  # "single" veya "range"
    T_s: Optional[float] = None  # Tek periyot modu için hedef periyot
    weight_type: str = "uniform"  # "uniform", "custom", "short_period", "long_period", "band"
    weight_params: Optional[Dict[str, Any]] = None  # Ağırlık parametreleri
    scale_limits: Optional[Tuple[float, float]] = None  # Ölçek katsayısı sınırları
    filter_criteria: Optional[Dict[str, Any]] = None  # Filtreleme kriterleri
    regulatory_checks: Optional[Dict[str, Any]] = None  # Yönetmelik kontrolleri
    n_top_records: int = 10  # En iyi N kayıt
    output_dir: str = "output"  # Çıktı dizini
    export_formats: List[str] = None  # Dışa aktarma formatları
    spectral_ordinate: str = "SRSS"  # "GM" veya "SRSS" (PGMD raporundaki "Spectral Ordinate" ile eşle)


class Scaling3DProcessor:
    """3B ölçekleme işlemlerini yöneten ana sınıf."""
    
    def __init__(self, config: Optional[Scaling3DConfig] = None):
        """
        Args:
            config: Ölçekleme konfigürasyonu
        """
        self.config = config or Scaling3DConfig()
        self.T_grid = build_period_grid()
        self.weights = None
        self.target_spectrum = None
        self.results = []
        self.metadata = []
        self.ranking = None
        self.regulatory_checks = {}
        
        # Varsayılan değerleri ayarla
        if self.config.export_formats is None:
            self.config.export_formats = ["json", "csv", "txt"]
    
    def set_target_spectrum(self, target_spectrum: np.ndarray) -> None:
        """
        Hedef spektrumu ayarlar.
        
        Args:
            target_spectrum: Hedef spektral ivme dizisi (301 nokta)
        """
        if len(target_spectrum) != 301:
            raise ValueError(f"Hedef spektrum 301 nokta olmalı, {len(target_spectrum)} bulundu")
        
        self.target_spectrum = target_spectrum
    
    def setup_weights(self) -> None:
        """Ağırlık fonksiyonunu ayarlar."""
        if self.config.weight_type == "uniform":
            self.weights = create_uniform_weights(self.T_grid)
        elif self.config.weight_type == "custom":
            if self.config.weight_params is None:
                raise ValueError("Özel ağırlık için parametreler gerekli")
            period_knots = self.config.weight_params["period_knots"]
            weight_knots = self.config.weight_params["weight_knots"]
            self.weights = create_weight_function(period_knots, weight_knots, self.T_grid)
        elif self.config.weight_type == "short_period":
            params = self.config.weight_params or {}
            from .weight_function import create_short_period_weights
            self.weights = create_short_period_weights(
                self.T_grid,
                params.get("T_cutoff", 1.0),
                params.get("decay_factor", 2.0)
            )
        elif self.config.weight_type == "long_period":
            params = self.config.weight_params or {}
            from .weight_function import create_long_period_weights
            self.weights = create_long_period_weights(
                self.T_grid,
                params.get("T_cutoff", 1.0),
                params.get("growth_factor", 2.0)
            )
        elif self.config.weight_type == "band":
            params = self.config.weight_params or {}
            from .weight_function import create_band_weights
            self.weights = create_band_weights(
                self.T_grid,
                params.get("T_center", 1.0),
                params.get("bandwidth", 0.5),
                params.get("shape", "gaussian")
            )
        else:
            raise ValueError(f"Bilinmeyen ağırlık tipi: {self.config.weight_type}")
        
        # Ağırlık doğrulama
        is_valid, message = validate_weight_function(self.weights, self.T_grid)
        if not is_valid:
            raise ValueError(f"Ağırlık fonksiyonu geçersiz: {message}")
    
    def process_records(
        self,
        records_data: List[Dict[str, Any]],
        metadata: Optional[List[RecordMetadata]] = None
    ) -> None:
        """
        Kayıtları işler ve ölçekleme yapar.
        
        Args:
            records_data: Kayıt verileri listesi
            metadata: Kayıt meta verileri
        """
        if self.target_spectrum is None:
            raise ValueError("Hedef spektrum ayarlanmamış")
        
        if self.weights is None:
            self.setup_weights()
        
        # Varsayılan meta veriler
        if metadata is None:
            metadata = [RecordMetadata() for _ in range(len(records_data))]
        
        # 3B ölçekleme
        # PGMD/PEER No Scaling uyumu için spekt. ordinatı GM varsayılan alınır
        self.results = scale_multiple_records_3d(
            self.target_spectrum,
            records_data,
            self.weights,
            self.config.mode,
            self.config.T_s,
            self.T_grid,
            self.config.scale_limits,
            spectral_ordinate=self.config.spectral_ordinate,
        )
        
        self.metadata = metadata
        
        # Sıralama
        self.ranking = rank_records_by_mse(self.results, self.metadata)
        
        # Filtreleme (varsa)
        if self.config.filter_criteria is not None:
            valid_indices, filtered_results, filtered_metadata = filter_records_by_criteria(
                self.results, self.metadata, self.config.filter_criteria
            )
            self.results = filtered_results
            self.metadata = filtered_metadata
            # Sıralamayı yeniden hesapla
            self.ranking = rank_records_by_mse(self.results, self.metadata)
    
    def perform_regulatory_checks(self, T_design: float) -> None:
        """
        Yönetmelik kontrollerini yapar.
        
        Args:
            T_design: Tasarım periyodu
        """
        if not self.results:
            raise ValueError("Önce kayıtları işleyin")
        
        # Varsayılan kontroller
        if self.config.regulatory_checks is None:
            self.config.regulatory_checks = create_default_checks()
        
        # Suite ortalaması hesapla
        suite_average = calculate_suite_averages(self.results, component="GM", T_grid=self.T_grid)
        
        # Kontrolleri yap
        self.regulatory_checks = perform_comprehensive_regulatory_checks(
            self.results,
            self.target_spectrum,
            T_design,
            component="GM",
            checks=self.config.regulatory_checks
        )
    
    def select_top_records(self) -> Tuple[List, List[RecordMetadata], List[int]]:
        """
        En iyi kayıtları seçer.
        
        Returns:
            Tuple[List, List[RecordMetadata], List[int]]: Seçilen kayıtlar
        """
        if not self.results:
            raise ValueError("Önce kayıtları işleyin")
        
        return select_top_records(
            self.results,
            self.metadata,
            self.config.n_top_records,
            self.config.filter_criteria
        )
    
    def generate_report(self, T_design: float) -> Dict[str, Any]:
        """
        Rapor oluşturur.
        
        Args:
            T_design: Tasarım periyodu
            
        Returns:
            Dict[str, Any]: Rapor verisi
        """
        if not self.results:
            raise ValueError("Önce kayıtları işleyin")
        
        # Yönetmelik kontrollerini yap
        if not self.regulatory_checks:
            self.perform_regulatory_checks(T_design)
        
        # Ölçekleme parametreleri
        scaling_params = {
            "mode": self.config.mode,
            "weight_type": self.config.weight_type,
            "T_s": self.config.T_s,
            "scale_limits": self.config.scale_limits,
            "n_records": len(self.results)
        }
        
        # Rapor oluştur
        report_data = create_scaling_report(
            self.results,
            self.metadata,
            self.ranking,
            self.regulatory_checks,
            self.target_spectrum,
            self.T_grid,
            scaling_params
        )
        
        return report_data
    
    def export_results(self, T_design: float, prefix: str = "scaling_3d") -> Dict[str, str]:
        """
        Sonuçları dışa aktarır.
        
        Args:
            T_design: Tasarım periyodu
            prefix: Dosya öneki
            
        Returns:
            Dict[str, str]: Oluşturulan dosya yolları
        """
        if not self.results:
            raise ValueError("Önce kayıtları işleyin")
        
        # Yönetmelik kontrollerini yap
        if not self.regulatory_checks:
            self.perform_regulatory_checks(T_design)
        
        # Ölçekleme parametreleri
        scaling_params = {
            "mode": self.config.mode,
            "weight_type": self.config.weight_type,
            "T_s": self.config.T_s,
            "scale_limits": self.config.scale_limits,
            "n_records": len(self.results)
        }
        
        # Kapsamlı rapor oluştur
        files_created = export_comprehensive_report(
            self.results,
            self.metadata,
            self.ranking,
            self.regulatory_checks,
            self.target_spectrum,
            self.T_grid,
            scaling_params,
            self.config.output_dir,
            prefix
        )
        
        return files_created
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        İstatistikleri döndürür.
        
        Returns:
            Dict[str, Any]: İstatistikler
        """
        if not self.results:
            return {}
        
        return calculate_selection_statistics(self.results, self.metadata)
    
    def get_suite_averages(self, component: str = "GM") -> Dict[str, Any]:
        """
        Suite ortalamalarını döndürür.
        
        Args:
            component: Bileşen
            
        Returns:
            Dict[str, Any]: Suite ortalaması sonuçları
        """
        if not self.results:
            return {}
        
        return calculate_suite_statistics(self.results, component)


def create_default_config() -> Scaling3DConfig:
    """
    Varsayılan konfigürasyon oluşturur.
    
    Returns:
        Scaling3DConfig: Varsayılan konfigürasyon
    """
    return Scaling3DConfig(
        mode="range",
        weight_type="uniform",
        scale_limits=(0.1, 10.0),
        filter_criteria=create_default_criteria(),
        regulatory_checks=create_default_checks(),
        n_top_records=10,
        output_dir="output",
        export_formats=["json", "csv", "txt"],
        spectral_ordinate="SRSS",
    )


# Test fonksiyonu
if __name__ == "__main__":
    # Test verisi oluştur
    T = build_period_grid()
    target_spectrum = 0.4 * np.ones_like(T)
    
    # Test kayıtları
    n_records = 3
    records_data = []
    metadata = []
    
    for i in range(n_records):
        record_data = {
            "SA_FN": (0.2 + i * 0.1) * np.ones_like(T),
            "SA_FP": (0.3 + i * 0.1) * np.ones_like(T),
            "SA_V": (0.25 + i * 0.1) * np.ones_like(T)
        }
        records_data.append(record_data)
        
        meta = RecordMetadata(
            nga_number=f"NGA{i+1:04d}",
            pulse=i % 2 == 0,
            duration_5_95=10.0 + i * 5.0,
            r_rup=10.0 + i * 20.0,
            vs30=200.0 + i * 100.0
        )
        metadata.append(meta)
    
    # 3B ölçekleme işlemi
    config = create_default_config()
    processor = Scaling3DProcessor(config)
    
    # Hedef spektrumu ayarla
    processor.set_target_spectrum(target_spectrum)
    
    # Kayıtları işle
    processor.process_records(records_data, metadata)
    
    # Yönetmelik kontrollerini yap
    processor.perform_regulatory_checks(T_design=1.0)
    
    # Rapor oluştur
    report_data = processor.generate_report(T_design=1.0)
    print(f"Rapor oluşturuldu: {len(report_data)} anahtar")
    
    # İstatistikler
    stats = processor.get_statistics()
    print(f"\nİstatistikler:")
    print(f"MSE: {stats.get('mse_mean', 0):.6f} ± {stats.get('mse_std', 0):.6f}")
    print(f"Ölçek katsayısı: {stats.get('f_mean', 0):.6f} ± {stats.get('f_std', 0):.6f}")
    
    # Suite ortalamaları
    suite_stats = processor.get_suite_averages(component="GM")
    print(f"\nSuite ortalamaları:")
    print(f"Kayıt sayısı: {suite_stats.get('n_records', 0)}")
    
    # Sonuçları dışa aktar
    try:
        files_created = processor.export_results(T_design=1.0)
        print(f"\nDışa aktarma başarılı:")
        for file_type, file_path in files_created.items():
            print(f"  {file_type}: {file_path}")
    except Exception as e:
        print(f"Dışa aktarma hatası: {e}")
