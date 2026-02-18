"""
PEER Ağırlık Fonksiyonu - Aralık Dışı Sıfır Kontrolü
====================================================

Kritik Test: np.interp left=0.0, right=0.0 kontrolü
"""

import numpy as np
import pytest
from src.scaling.weight_function import create_weight_function
from src.scaling.period_grid import build_period_grid


class TestWeightFunctionBoundary:
    """Ağırlık fonksiyonu aralık dışı sıfır testi"""
    
    def test_out_of_range_zeros(self):
        """
        Test 1: Aralık Dışı Değerler Sıfır Olmalı (PEER Kritik)
        
        PEER Mantığı: Kullanıcı tanımlı periyot düğümlerinin dışındaki
        periyotlara ağırlık 0 atanmalı.
        
        Örnek: period_knots = [0.5, 1.0, 2.0]
        → T < 0.5 için w = 0
        → T > 2.0 için w = 0
        """
        T_grid = build_period_grid()  # 0.01 - 10.0 s
        
        # Dar bir band tanımla: 0.5 - 2.0 s
        period_knots = np.array([0.5, 1.0, 2.0])
        weight_knots = np.array([0.0, 1.0, 0.0])  # 1.0s'de pik
        
        w = create_weight_function(period_knots, weight_knots, T_grid)
        
        # Aralık dışı kontroller
        # T < 0.5 için w = 0
        mask_below = T_grid < 0.5
        assert np.all(w[mask_below] == 0.0), \
            f"T < 0.5 için ağırlık 0 olmalı, ancak {w[mask_below].max():.6f} bulundu"
        
        # T > 2.0 için w = 0
        mask_above = T_grid > 2.0
        assert np.all(w[mask_above] == 0.0), \
            f"T > 2.0 için ağırlık 0 olmalı, ancak {w[mask_above].max():.6f} bulundu"
        
        print("✅ Test 1 GEÇTI: Aralık dışı ağırlıklar 0")
    
    def test_narrow_band(self):
        """
        Test 2: Dar Bant - Çok Küçük Aralık
        
        Çok dar bir periyot aralığı tanımlandığında da doğru çalışmalı
        """
        T_grid = build_period_grid()
        
        # Çok dar band: 0.95 - 1.05 s (sadece 1.0s civarı)
        period_knots = np.array([0.95, 1.0, 1.05])
        weight_knots = np.array([0.5, 1.0, 0.5])
        
        w = create_weight_function(period_knots, weight_knots, T_grid)
        
        # T < 0.95 için sıfır
        assert np.all(w[T_grid < 0.95] == 0.0), "T < 0.95 için sıfır değil"
        
        # T > 1.05 için sıfır
        assert np.all(w[T_grid > 1.05] == 0.0), "T > 1.05 için sıfır değil"
        
        # [0.95, 1.05] aralığında pozitif
        mask_inside = (T_grid >= 0.95) & (T_grid <= 1.05)
        assert np.any(w[mask_inside] > 0.0), "Aralık içinde ağırlık yok"
        
        print("✅ Test 2 GEÇTI: Dar bant doğru")
    
    def test_wide_band(self):
        """
        Test 3: Geniş Bant - Tüm Grid'i Kapsayan
        
        Periyot düğümleri grid'in tamamını kapsıyorsa hiçbir yerde 0 olmamalı
        """
        T_grid = build_period_grid()  # 0.01 - 10.0 s
        
        # Grid'den daha geniş: 0.005 - 15.0 s
        period_knots = np.array([0.005, 0.1, 1.0, 10.0, 15.0])
        weight_knots = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
        
        w = create_weight_function(period_knots, weight_knots, T_grid)
        
        # Tüm grid noktalarında w > 0 olmalı
        assert np.all(w > 0.0), "Grid kapsamında sıfır ağırlık var (hata!)"
        
        print("✅ Test 3 GEÇTI: Geniş bant doğru")
    
    def test_normalization(self):
        """
        Test 4: Normalizasyon Kontrolü
        
        Aralık dışı sıfırlar olsa bile normalize edilmiş toplam = 1.0 olmalı
        """
        T_grid = build_period_grid()
        
        # Dar band
        period_knots = np.array([0.2, 1.0, 3.0])
        weight_knots = np.array([1.0, 5.0, 1.0])
        
        w = create_weight_function(period_knots, weight_knots, T_grid)
        
        # Toplam = 1.0
        assert np.isclose(np.sum(w), 1.0, rtol=1e-10), \
            f"Ağırlık toplamı 1.0 olmalı, {np.sum(w):.10f} bulundu"
        
        print("✅ Test 4 GEÇTI: Normalizasyon doğru")
    
    def test_before_vs_after_fix(self):
        """
        Test 5: Düzeltme Öncesi vs Sonrası
        
        left/right parametreleri olmadan np.interp ne yapardı?
        Bu test düzeltmenin etkisini gösterir.
        """
        T_grid = build_period_grid()
        
        # Dar band
        period_knots = np.array([0.5, 1.0, 2.0])
        # Uç düğümler sıfır olmadığı durumda yanlış yöntem uçlarda dolgu yapar
        weight_knots = np.array([0.3, 1.0, 0.3])
        
        log_T_knots = np.log10(period_knots)
        log_T_grid = np.log10(T_grid)
        
        # YANLIŞ yöntem (left/right yok)
        w_wrong = np.interp(log_T_grid, log_T_knots, weight_knots)
        
        # DOĞRU yöntem (left=0.0, right=0.0)
        w_correct = np.interp(log_T_grid, log_T_knots, weight_knots,
                             left=0.0, right=0.0)
        
        # Aralık dışı fark kontrolü
        mask_below = T_grid < 0.5
        mask_above = T_grid > 2.0
        
        # Yanlış yöntemde sıfır OLMAYACAK (uç değer dolgusu)
        assert not np.all(w_wrong[mask_below] == 0.0), \
            "Yanlış yöntem sıfır döndürdü (beklenmeyen!)"
        
        # Doğru yöntemde sıfır OLMALI
        assert np.all(w_correct[mask_below] == 0.0), \
            "Doğru yöntem sıfır döndürmedi (hata!)"
        assert np.all(w_correct[mask_above] == 0.0), \
            "Doğru yöntem sıfır döndürmedi (hata!)"
        
        print("✅ Test 5 GEÇTI: Düzeltme etkili")
        print(f"   Yanlış: T<0.5 max = {w_wrong[mask_below].max():.6f} (≠0)")
        print(f"   Doğru:  T<0.5 max = {w_correct[mask_below].max():.6f} (=0)")
    
    def test_single_period_weight(self):
        """
        Test 6: Tek Periyot Ağırlığı
        
        Çok dar band: Tek periyot civarında ağırlık
        """
        T_grid = build_period_grid()
        
        # 1.0s civarında çok dar
        period_knots = np.array([0.99, 1.0, 1.01])
        weight_knots = np.array([0.0, 1.0, 0.0])
        
        w = create_weight_function(period_knots, weight_knots, T_grid)
        
        # T < 0.99 için sıfır
        assert np.all(w[T_grid < 0.99] == 0.0)
        
        # T > 1.01 için sıfır
        assert np.all(w[T_grid > 1.01] == 0.0)
        
        # Toplam hala 1.0
        assert np.isclose(np.sum(w), 1.0, rtol=1e-10)
        
        print("✅ Test 6 GEÇTI: Tek periyot ağırlığı doğru")


class TestWeightFunctionReport:
    """Ağırlık fonksiyonu test raporu"""
    
    def test_full_report(self):
        """Tüm testleri çalıştır ve rapor üret"""
        print("\n" + "="*70)
        print("PEER Ağırlık Fonksiyonu - Aralık Dışı Sıfır Testi")
        print("="*70)
        
        test_obj = TestWeightFunctionBoundary()
        tests = [
            ("Aralık Dışı Sıfır (Kritik)", "test_out_of_range_zeros"),
            ("Dar Bant", "test_narrow_band"),
            ("Geniş Bant", "test_wide_band"),
            ("Normalizasyon", "test_normalization"),
            ("Düzeltme Öncesi/Sonrası", "test_before_vs_after_fix"),
            ("Tek Periyot Ağırlığı", "test_single_period_weight"),
        ]
        
        passed = 0
        failed = 0
        
        for name, test_name in tests:
            try:
                getattr(test_obj, test_name)()
                print(f"✅ {name:40s} GEÇTI")
                passed += 1
            except Exception as e:
                print(f"❌ {name:40s} KALDI: {str(e)}")
                failed += 1
        
        print("="*70)
        print(f"Toplam: {passed + failed} | Geçti: {passed} | Kaldı: {failed}")
        print("="*70)
        
        if failed == 0:
            print("🎉 TÜM TESTLER BAŞARILI - left=0.0, right=0.0 DOĞRU!")
        
        assert failed == 0, f"{failed} test başarısız"


if __name__ == "__main__":
    import sys
    pytest.main([__file__, "-v", "--tb=short"])

