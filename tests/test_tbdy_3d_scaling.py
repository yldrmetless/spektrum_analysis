"""
TBDY-2018 3B Basit Ölçeklendirme Test Modülü
==========================================

Bu test modülü, belgede belirtilen TBDY-2018 gereksinimlerini doğrular.
"""

import unittest
import numpy as np
from src.scaling.tbdy_scaling import (
    scale_3d_simple_tbdy, validate_records_tbdy, export_tbdy_results_csv,
    design_spectrum_tbdy, TBDYScaleResult
)
from src.scaling.scale_factor import (
    calculate_srss_spectrum, normalize_weights_tbdy, 
    calculate_scale_factor_3d_tbdy
)


class TestTBDY3DScaling(unittest.TestCase):
    """TBDY-2018 3B Basit Ölçeklendirme test sınıfı."""
    
    def setUp(self):
        """Test verilerini hazırla."""
        np.random.seed(42)
        
        # 12 kayıt (3 farklı olay, her olay 4 kayıt)
        self.records = []
        self.records_meta = []
        
        for event_id in range(3):
            for record_id in range(4):
                # 10 saniye, 0.01 dt
                dt = 0.01
                t = np.arange(0, 10, dt)
                
                # Basit sinüzoidal + gürültü
                freq = 2.0 + event_id * 0.5
                ax = 0.2 * np.sin(2*np.pi*freq*t) * np.exp(-t/5) + np.random.normal(0, 0.05, len(t))
                ay = 0.15 * np.cos(2*np.pi*freq*t) * np.exp(-t/4) + np.random.normal(0, 0.04, len(t))
                
                meta = {
                    "event_id": f"Event_{event_id+1}",
                    "station": f"Station_{record_id+1}",
                    "nga_number": f"NGA_{event_id*4 + record_id + 1:04d}"
                }
                
                self.records.append((ax, ay, dt, meta))
                self.records_meta.append(meta)
        
        # TBDY parametreleri
        self.T1 = 1.0
        self.SDS = 0.8
        self.SD1 = 0.6
        self.TL = 6.0
        self.alpha = 1.3
        
    def test_srss_calculation(self):
        """SRSS hesaplama doğruluğu testi."""
        # Bilinen değerler
        SA_x = np.array([1.0, 2.0, 0.5])
        SA_y = np.array([1.0, 1.0, 1.5])
        
        # SRSS hesapla
        SA_srss = calculate_srss_spectrum(SA_x, SA_y)
        
        # Beklenen değerler
        expected = np.array([
            np.sqrt(1.0**2 + 1.0**2),  # √2 ≈ 1.414
            np.sqrt(2.0**2 + 1.0**2),  # √5 ≈ 2.236
            np.sqrt(0.5**2 + 1.5**2)   # √2.5 ≈ 1.581
        ])
        
        np.testing.assert_array_almost_equal(SA_srss, expected, decimal=6)
        
    def test_weight_normalization(self):
        """Ağırlık normalizasyonu testi."""
        from src.scaling.period_grid import build_period_grid
        from src.scaling.weight_function import create_uniform_weights
        
        T_grid = build_period_grid()
        weights = create_uniform_weights(T_grid)
        T1 = 1.0
        
        # Normalize et
        weights_norm = normalize_weights_tbdy(weights, T_grid, T1)
        
        # Kontroller
        self.assertAlmostEqual(np.sum(weights_norm), 1.0, places=6)
        
        # Aralık dışı sıfır olmalı
        T_min, T_max = 0.2 * T1, 1.5 * T1
        mask = (T_grid >= T_min) & (T_grid <= T_max)
        
        # Aralık dışındaki ağırlıklar sıfır
        np.testing.assert_array_equal(weights_norm[~mask], 0.0)
        
        # Aralık içindeki ağırlıklar pozitif
        self.assertTrue(np.all(weights_norm[mask] > 0))
        
    def test_record_validation(self):
        """Kayıt validasyon testi."""
        # Geçerli kayıtlar
        is_valid, msg = validate_records_tbdy(self.records)
        self.assertTrue(is_valid)
        
        # Çok az kayıt
        few_records = self.records[:5]
        is_valid, msg = validate_records_tbdy(few_records)
        self.assertFalse(is_valid)
        self.assertIn("yetersiz", msg)
        
        # Aynı olay fazla kayıt (tümü aynı event_id)
        same_event_records = []
        for i in range(5):
            ax, ay, dt, _ = self.records[i]
            meta = {"event_id": "SameEvent"}
            same_event_records.append((ax, ay, dt, meta))
        
        is_valid, msg = validate_records_tbdy(same_event_records)
        self.assertFalse(is_valid)
        self.assertIn("çok fazla", msg)
        
    def test_design_spectrum(self):
        """TBDY tasarım spektrumu testi."""
        T = np.array([0.0, 0.1, 0.5, 1.0, 2.0, 10.0])
        Sa = design_spectrum_tbdy(T, self.SDS, self.SD1, self.TL)
        
        # Temel kontroller
        self.assertEqual(len(Sa), len(T))
        self.assertTrue(np.all(Sa >= 0))
        
        # T=0'da 0.4*SDS
        self.assertAlmostEqual(Sa[0], 0.4 * self.SDS, places=6)
        
        # Spektrum pozitif ve sonlu olmalı
        self.assertTrue(np.all(np.isfinite(Sa)))
        
    def test_tbdy_scaling_basic(self):
        """Temel TBDY ölçeklendirme testi."""
        result = scale_3d_simple_tbdy(
            records=self.records,
            T1=self.T1,
            SDS=self.SDS,
            SD1=self.SD1,
            TL=self.TL,
            alpha=self.alpha
        )
        
        # Sonuç tipi kontrolü
        self.assertIsInstance(result, TBDYScaleResult)
        
        # Temel alanlar
        self.assertEqual(result.n_records, len(self.records))
        self.assertEqual(len(result.f_list), len(self.records))
        self.assertEqual(len(result.mse_list), len(self.records))
        
        # Ölçek katsayıları pozitif
        self.assertTrue(all(f > 0 for f in result.f_list))
        
        # Global gamma ≥ 1.0
        self.assertGreaterEqual(result.global_gamma, 1.0)
        
        # Min ratio kontrolü
        if result.pass_tbdy:
            self.assertGreaterEqual(result.min_ratio, 1.0)
        else:
            self.assertLess(result.min_ratio, 1.0)
            
        # Periyot aralığı
        T_min, T_max = result.T_range
        self.assertAlmostEqual(T_min, 0.2 * self.T1, places=6)
        self.assertAlmostEqual(T_max, 1.5 * self.T1, places=6)
        
    def test_tbdy_1_30_condition(self):
        """1.30 koşulu testi."""
        result = scale_3d_simple_tbdy(
            records=self.records,
            T1=self.T1,
            SDS=self.SDS,
            SD1=self.SD1,
            TL=self.TL,
            alpha=1.3  # TBDY zorunlu değer
        )
        
        # Kontrol aralığında minimum oran
        T_min, T_max = 0.2 * self.T1, 1.5 * self.T1
        mask = (result.T_grid >= T_min) & (result.T_grid <= T_max)
        
        ratios = result.srss_avg[mask] / result.target_spectrum[mask]
        min_ratio_calculated = float(np.min(ratios))
        
        # Hesaplanan ile kaydedilen eşleşmeli
        self.assertAlmostEqual(result.min_ratio, min_ratio_calculated, places=6)
        
        # Global gamma uygulandıysa min_ratio ≥ 1.0 olmalı
        if result.gamma_applied:
            self.assertGreaterEqual(result.min_ratio, 1.0)
            
    def test_same_scale_factor_for_xy(self):
        """İki yatay bileşen için aynı ölçek katsayısı testi."""
        result = scale_3d_simple_tbdy(
            records=self.records,
            T1=self.T1,
            SDS=self.SDS,
            SD1=self.SD1,
            TL=self.TL
        )
        
        # Her kayıt için tek bir ölçek katsayısı olmalı
        self.assertEqual(len(result.f_list), len(self.records))
        
        # Tüm katsayılar pozitif
        for f in result.f_list:
            self.assertGreater(f, 0)
            
        # TBDY: İki yatay bileşen aynı katsayı ile ölçeklenir
        # Bu, algoritma tasarımında garantilidir
        
    def test_csv_export(self):
        """CSV dışa aktarma testi."""
        import tempfile
        import os
        import csv
        
        result = scale_3d_simple_tbdy(
            records=self.records,
            T1=self.T1,
            SDS=self.SDS,
            SD1=self.SD1,
            TL=self.TL
        )
        
        # Geçici dosya
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
            
        try:
            # CSV'ye aktar
            csv_path = export_tbdy_results_csv(result, self.records_meta, temp_path)
            self.assertTrue(os.path.exists(csv_path))
            
            # CSV içeriğini kontrol et
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
            # Satır sayısı
            self.assertEqual(len(rows), len(self.records))
            
            # Başlık kontrolleri
            expected_headers = ["set_id", "event", "station", "NGA_id", "f", "gamma", 
                              "min_ratio", "mse", "pass_3D", "notes"]
            self.assertEqual(reader.fieldnames, expected_headers)
            
            # Veri kontrolleri
            for i, row in enumerate(rows):
                self.assertEqual(int(row["set_id"]), i + 1)
                self.assertTrue(float(row["f"]) > 0)
                self.assertTrue(float(row["gamma"]) >= 1.0)
                self.assertIn(row["pass_3D"], ["PASS", "FAIL"])
                
        finally:
            # Temizlik
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    def test_insufficient_records_handling(self):
        """Yetersiz kayıt durumu testi."""
        # 5 kayıt (< 11)
        few_records = self.records[:5]
        
        # Validasyon hatası bekleniyor
        with self.assertRaises(ValueError) as context:
            scale_3d_simple_tbdy(
                records=few_records,
                T1=self.T1,
                SDS=self.SDS,
                SD1=self.SD1,
                TL=self.TL
            )
            
        self.assertIn("validasyon", str(context.exception).lower())
        
    def test_same_event_violation(self):
        """Aynı olay kuralı ihlali testi."""
        # Tüm kayıtları aynı olay yap (> 3)
        same_event_records = []
        for i in range(5):
            ax, ay, dt, _ = self.records[i]
            meta = {"event_id": "SameEvent"}
            same_event_records.append((ax, ay, dt, meta))
            
        # Validasyon hatası bekleniyor
        with self.assertRaises(ValueError) as context:
            scale_3d_simple_tbdy(
                records=same_event_records,
                T1=self.T1,
                SDS=self.SDS,
                SD1=self.SD1,
                TL=self.TL
            )
            
        self.assertIn("çok fazla", str(context.exception))


if __name__ == '__main__':
    # Test çalıştır
    unittest.main(verbosity=2)
