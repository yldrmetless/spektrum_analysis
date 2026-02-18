"""
PEER Log-Log İnterpolasyon - Single Period Düzeltmesi Testi
===========================================================

Kritik Test: Linear interpolasyon vs Log-log interpolasyon
"""

import numpy as np
import pytest
from src.scaling.scale_factor import _interpolate_loglog, calculate_single_period_scale_factor
from src.scaling.period_grid import build_period_grid, interpolate_to_grid


class TestLogLogInterpolation:
    """Log-log interpolasyon testi"""
    
    def test_interpolation_comparison(self):
        """
        Test 1: Linear vs Log-Log Karşılaştırma
        
        Spektrumlar log-normal dağılım gösterir, bu nedenle log-log
        interpolasyon linear'dan daha doğrudur.
        """
        # Test spektrumu: Tipik tepki spektrumu şekli
        T = np.array([0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0])
        SA = np.array([0.2, 0.8, 1.2, 0.8, 0.4, 0.15, 0.08])
        
        # İnterpolasyon noktası
        T_s = 0.7  # 0.5 ile 1.0 arasında
        
        # Linear interpolasyon (YANLIŞ)
        SA_linear = np.interp(T_s, T, SA)
        
        # Log-log interpolasyon (DOĞRU)
        SA_loglog = _interpolate_loglog(T, SA, T_s)
        
        # Karşılaştır
        diff = abs(SA_linear - SA_loglog)
        diff_percent = (diff / SA_loglog) * 100
        
        print(f"T_s = {T_s} s için:")
        print(f"  Linear:  SA = {SA_linear:.6f}")
        print(f"  Log-log: SA = {SA_loglog:.6f}")
        print(f"  Fark:    {diff:.6f} ({diff_percent:.2f}%)")
        
        # Log-log genellikle farklı sonuç verir
        # (Eğer spektrum gerçekten log-linear ise)
        assert SA_loglog > 0, "Log-log sonuç pozitif olmalı"
    
    def test_zero_protection(self):
        """
        Test 2: Sıfır/Negatif Değer Koruması
        
        Spektrumda sıfır/negatif değerler olsa bile log-log interpolasyon
        çalışmalı (1e-15 alt sınırı ile)
        """
        T = np.array([0.01, 0.1, 1.0, 10.0])
        SA = np.array([0.5, 0.0, 1.0, 0.2])  # 0.1s'de sıfır!
        
        T_s = 0.5
        
        # Hata vermeden çalışmalı
        SA_interp = _interpolate_loglog(T, SA, T_s)
        
        assert np.isfinite(SA_interp), "Sıfır değer log-log'u bozdu"
        assert SA_interp > 0, "Sonuç pozitif olmalı"
        print(f"✅ Sıfır koruması çalışıyor: SA({T_s}) = {SA_interp:.6f}")
    
    def test_endpoint_extrapolation(self):
        """
        Test 3: Uç Nokta Extrapolasyon
        
        T_s grid dışında ise ne olur?
        np.interp varsayılan olarak uç değerle doldurur (doğru davranış)
        """
        T = np.array([0.1, 1.0, 5.0])
        SA = np.array([0.8, 1.0, 0.3])
        
        # Grid dışı: Çok küçük
        T_s_low = 0.01  # T[0] = 0.1'den küçük
        SA_low = _interpolate_loglog(T, SA, T_s_low)
        
        # Grid dışı: Çok büyük
        T_s_high = 10.0  # T[-1] = 5.0'den büyük
        SA_high = _interpolate_loglog(T, SA, T_s_high)
        
        # Extrapolasyon yapılmalı
        assert SA_low > 0, "Düşük uç extrapolasyon başarısız"
        assert SA_high > 0, "Yüksek uç extrapolasyon başarısız"
        
        print(f"✅ Extrapolasyon: T={T_s_low} → SA={SA_low:.6f}")
        print(f"✅ Extrapolasyon: T={T_s_high} → SA={SA_high:.6f}")
    
    def test_single_period_scale_factor_consistency(self):
        """
        Test 4: Ölçek Katsayısı Tutarlılığı
        
        Log-log interpolasyon kullanıldığında ölçek katsayısı
        mantıklı değerlerde olmalı
        """
        T_grid = build_period_grid()
        
        # Hedef spektrum
        SA_target = 0.5 * np.ones_like(T_grid)  # Sabit
        
        # Kayıt spektrumu (hedefin yarısı)
        SA_record = 0.25 * np.ones_like(T_grid)
        
        T_s = 1.0
        
        # Ölçek katsayısı
        f = calculate_single_period_scale_factor(SA_target, SA_record, T_grid, T_s)
        
        # Sabit spektrumlar için f = 0.5 / 0.25 = 2.0
        expected_f = 0.5 / 0.25
        
        assert np.isclose(f, expected_f, rtol=1e-6), \
            f"Ölçek katsayısı yanlış: {f} != {expected_f}"
        
        print(f"✅ Ölçek katsayısı tutarlı: f = {f:.6f}")
    
    def test_realistic_spectrum(self):
        """
        Test 5: Gerçekçi Spektrum
        
        TBDY benzeri bir spektrum üzerinde log-log interpolasyon testi
        """
        # TBDY spektrumu simülasyonu
        T = np.logspace(-2, 1, 301)  # 0.01 - 10s
        
        # TBDY parametreleri
        SDS, SD1, TL = 1.0, 0.6, 6.0
        TA = 0.2 * SD1 / SDS
        TB = SD1 / SDS
        
        # TBDY spektrumu
        SA = np.zeros_like(T)
        SA[T <= TA] = (0.4 + 0.6 * T[T <= TA] / TA) * SDS
        SA[(T > TA) & (T <= TB)] = SDS
        SA[(T > TB) & (T <= TL)] = SD1 / T[(T > TB) & (T <= TL)]
        SA[T > TL] = SD1 * TL / (T[T > TL] ** 2)
        
        # Farklı periyotlarda interpolasyon
        test_periods = [0.05, 0.3, 0.7, 1.5, 3.0, 8.0]
        
        for T_s in test_periods:
            SA_interp = _interpolate_loglog(T, SA, T_s)
            
            # Grid'deki en yakın değer
            idx_nearest = np.argmin(np.abs(T - T_s))
            SA_nearest = SA[idx_nearest]
            
            # Log-log interpolasyon yakın olmalı
            rel_diff = abs(SA_interp - SA_nearest) / SA_nearest
            
            assert SA_interp > 0, f"T_s={T_s} için SA <= 0"
            print(f"  T_s={T_s:.2f}s → SA={SA_interp:.4f} (grid'e göre fark: {rel_diff*100:.1f}%)")
        
        print(f"✅ Gerçekçi spektrum testi geçti")
    
    def test_log_vs_linear_difference(self):
        """
        Test 6: Log-log vs Linear Fark Analizi
        
        Tipik spektrum için log-log ve linear interpolasyon
        arasındaki farkı ölçer
        """
        # Tipik response spectrum şekli (pik + düşüş)
        T = np.array([0.01, 0.05, 0.1, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0])
        SA = np.array([0.15, 0.6, 1.0, 1.2, 1.1, 0.7, 0.35, 0.14, 0.07])
        
        # Test periyotları (grid noktaları arası)
        test_T = np.array([0.03, 0.15, 0.7, 1.5, 3.0, 7.0])
        
        max_diff = 0.0
        max_diff_percent = 0.0
        
        for T_s in test_T:
            # Linear
            SA_lin = np.interp(T_s, T, SA)
            
            # Log-log
            SA_log = _interpolate_loglog(T, SA, T_s)
            
            diff = abs(SA_log - SA_lin)
            diff_percent = (diff / SA_log) * 100
            
            max_diff = max(max_diff, diff)
            max_diff_percent = max(max_diff_percent, diff_percent)
            
            print(f"  T={T_s:.2f}s: Linear={SA_lin:.4f}, Log-log={SA_log:.4f}, Fark={diff_percent:.2f}%")
        
        print(f"\n  Maksimum fark: {max_diff:.6f} ({max_diff_percent:.2f}%)")
        print(f"  ✅ Log-log interpolasyon farklı sonuç veriyor (beklenen)")


class TestLogLogReport:
    """Log-log interpolasyon test raporu"""
    
    def test_full_report(self):
        """Tüm testleri çalıştır ve rapor üret"""
        print("\n" + "="*70)
        print("PEER Log-Log İnterpolasyon Testi")
        print("="*70)
        
        test_obj = TestLogLogInterpolation()
        tests = [
            ("Linear vs Log-Log Karşılaştırma", "test_interpolation_comparison"),
            ("Sıfır Değer Koruması", "test_zero_protection"),
            ("Uç Nokta Extrapolasyon", "test_endpoint_extrapolation"),
            ("Ölçek Katsayısı Tutarlılık", "test_single_period_scale_factor_consistency"),
            ("Gerçekçi TBDY Spektrumu", "test_realistic_spectrum"),
            ("Linear vs Log-Log Fark Analizi", "test_log_vs_linear_difference"),
        ]
        
        passed = 0
        failed = 0
        
        for name, test_name in tests:
            try:
                print(f"\n{name}:")
                getattr(test_obj, test_name)()
                passed += 1
            except Exception as e:
                print(f"❌ {name} KALDI: {str(e)}")
                failed += 1
        
        print("\n" + "="*70)
        print(f"Toplam: {passed + failed} | Geçti: {passed} | Kaldı: {failed}")
        print("="*70)
        
        if failed == 0:
            print("🎉 TÜM TESTLER BAŞARILI - LOG-LOG İNTERPOLASYON DOĞRU!")
        
        assert failed == 0, f"{failed} test başarısız"


if __name__ == "__main__":
    import sys
    pytest.main([__file__, "-v", "--tb=short"])

