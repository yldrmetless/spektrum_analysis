"""
PEER Significant Duration Spesifikasyonu Uygunluk Testleri
===========================================================

PEER_Significant_Duration_Spec.md'deki QA/Test Direktiflerine göre
"""

import numpy as np
import pytest
from src.calculations.earthquake_stats import EarthquakeStats


class TestPEERSignificantDuration:
    """PEER Significant Duration spesifikasyon testleri"""
    
    def test_amplitude_invariance(self):
        """
        Test 1: Amplitüd Değişmezliği
        
        PEER Gereksinimi: Amplitüd ölçeklemesi süreyi değiştirmemeli
        acc, 10*acc için D5-75 ve D5-95 aynı olmalı
        """
        # Test verisi: Basit sinüs dalgası
        dt = 0.01
        t = np.arange(0, 10, dt)
        acc = 0.1 * np.sin(2 * np.pi * t) * np.exp(-t/5)  # Azalan sinüs
        
        # Orijinal
        d1 = EarthquakeStats.calculate_D5_95(acc, dt, 'm/s²')
        
        # 10x ölçeklenmiş
        acc_scaled = 10 * acc
        d2 = EarthquakeStats.calculate_D5_95(acc_scaled, dt, 'm/s²')
        
        # Süreler aynı olmalı (sayısal hata toleransı ile)
        assert np.isclose(d1.duration, d2.duration, rtol=1e-10), \
            f"Amplitüd ölçeklemesi süreyi değiştirdi: {d1.duration} != {d2.duration}"
        
        # D5-75 için de kontrol
        d1_75 = EarthquakeStats.calculate_D5_75(acc, dt, 'm/s²')
        d2_75 = EarthquakeStats.calculate_D5_75(acc_scaled, dt, 'm/s²')
        
        assert np.isclose(d1_75.duration, d2_75.duration, rtol=1e-10), \
            f"D5-75 amplitüd değişmezliği ihlal edildi"
    
    def test_duration_ordering(self):
        """
        Test 2: Süre Sıralaması
        
        PEER Gereksinimi: D5-75 ≤ D5-95 daima True olmalı
        """
        # Rastgele test verisi
        np.random.seed(42)
        dt = 0.01
        t = np.arange(0, 20, dt)
        acc = 0.2 * np.random.randn(len(t)) * np.exp(-t/10)
        
        d_75 = EarthquakeStats.calculate_D5_75(acc, dt, 'g')
        d_95 = EarthquakeStats.calculate_D5_95(acc, dt, 'g')
        
        assert d_75.duration <= d_95.duration, \
            f"D5-75 ({d_75.duration}) > D5-95 ({d_95.duration})"
    
    def test_unit_equivalence(self):
        """
        Test 3: Birim Denkliği
        
        PEER Gereksinimi: unit='g' ve unit='m/s²' sonuçları eşit olmalı (süreler)
        """
        dt = 0.01
        t = np.arange(0, 15, dt)
        acc_g = 0.15 * np.sin(2 * np.pi * 0.5 * t) * np.exp(-t/8)
        acc_ms2 = acc_g * 9.80665  # g → m/s²
        
        # g ile hesapla
        d1 = EarthquakeStats.calculate_D5_95(acc_g, dt, 'g')
        
        # m/s² ile hesapla
        d2 = EarthquakeStats.calculate_D5_95(acc_ms2, dt, 'm/s²')
        
        # Süreler aynı olmalı
        assert np.isclose(d1.duration, d2.duration, rtol=1e-10), \
            f"Birim dönüşümü süreyi değiştirdi: g={d1.duration}, m/s²={d2.duration}"
    
    def test_invalid_dt(self):
        """
        Test 4: Geçersiz dt
        
        PEER Gereksinimi: dt ≤ 0 ise hata fırlatmalı
        """
        acc = np.random.randn(100)
        
        with pytest.raises(ValueError, match="dt must be positive"):
            EarthquakeStats.calculate_D5_95(acc, 0.0, 'g')
        
        with pytest.raises(ValueError, match="dt must be positive"):
            EarthquakeStats.calculate_D5_95(acc, -0.01, 'g')
    
    def test_invalid_record(self):
        """
        Test 5: Bozuk Kayıt
        
        PEER Gereksinimi: E_total ≤ 0 ise NaN döndürmeli
        """
        dt = 0.01
        
        # Tüm sıfır
        acc_zero = np.zeros(1000)
        d = EarthquakeStats.calculate_D5_95(acc_zero, dt, 'g')
        assert np.isnan(d.duration), "Sıfır kayıt için NaN dönmedi"
        
        # Tüm NaN
        acc_nan = np.full(1000, np.nan)
        d = EarthquakeStats.calculate_D5_95(acc_nan, dt, 'g')
        assert np.isnan(d.duration), "NaN kayıt için NaN dönmedi"
    
    def test_monotonicity(self):
        """
        Test 6: F Dizisi Monotonluğu
        
        PEER Gereksinimi: F = np.maximum.accumulate(F) sonrası azalmamalı
        
        Not: Bu dahili bir testtir, kodun doğruluğunu kontrol eder
        """
        # Sayısal hataya yol açabilecek veri
        dt = 0.005
        t = np.arange(0, 10, dt)
        acc = 0.1 * (np.sin(10 * np.pi * t) + 0.1 * np.random.randn(len(t)))
        
        # Hesaplama normal çalışmalı (dahili olarak monotonluk garantisi var)
        d = EarthquakeStats.calculate_D5_95(acc, dt, 'g')
        
        # Sonuç geçerli olmalı
        assert np.isfinite(d.duration), "Monotonluk garantisi başarısız"
        assert d.duration >= 0, "Negatif süre hesaplandı"
    
    def test_two_components_max(self):
        """
        Test 7: İki Bileşen - MAX Özeti
        
        PEER Önerisi: İki bileşen için MAX(FN, FP) kullanılmalı
        """
        dt = 0.01
        t = np.arange(0, 15, dt)
        
        # FN: Daha uzun süreli
        acc_fn = 0.1 * np.sin(2 * np.pi * 0.3 * t) * np.exp(-t/10)
        
        # FP: Daha kısa süreli
        acc_fp = 0.1 * np.sin(2 * np.pi * 0.5 * t) * np.exp(-t/6)
        
        result = EarthquakeStats.calculate_duration_two_components(
            acc_fn, acc_fp, dt, 5.0, 95.0, 'g', 'max'
        )
        
        # MAX doğru hesaplanmalı
        expected_max = max(result['fn'].duration, result['fp'].duration)
        assert np.isclose(result['summary'], expected_max, rtol=1e-10), \
            f"MAX özeti yanlış: {result['summary']} != {expected_max}"
        
        # MAX >= her iki bileşen
        assert result['summary'] >= result['fn'].duration
        assert result['summary'] >= result['fp'].duration
    
    def test_two_components_mean(self):
        """
        Test 8: İki Bileşen - MEAN Özeti (PEER Algorithms §5)
        
        PEER Algorithms önerisi: Takım düzeyinde aritmetik ortalama
        "Zaman büyüklüğünde geometrik ortalama fiziksel olarak anlamlı değildir"
        """
        dt = 0.01
        t = np.arange(0, 10, dt)
        acc_fn = 0.1 * np.sin(2 * np.pi * t) * np.exp(-t/5)
        acc_fp = 0.1 * np.cos(2 * np.pi * t) * np.exp(-t/5)
        
        result = EarthquakeStats.calculate_duration_two_components(
            acc_fn, acc_fp, dt, 5.0, 95.0, 'g', 'mean'
        )
        
        # MEAN doğru hesaplanmalı (aritmetik ortalama)
        expected_mean = (result['fn'].duration + result['fp'].duration) / 2.0
        assert np.isclose(result['summary'], expected_mean, rtol=1e-10), \
            f"MEAN özeti yanlış: {result['summary']} != {expected_mean}"
        
        # Geometrik ortalama KULLANILMAMALI (fiziksel olarak anlamsız)
        geometric_mean = np.sqrt(result['fn'].duration * result['fp'].duration)
        assert not np.isclose(result['summary'], geometric_mean, rtol=1e-6, atol=0.0), \
            "Hata: Geometrik ortalama kullanılmış (yanlış!)"
    
    def test_convenience_functions(self):
        """
        Test 9: Kolaylık Fonksiyonları
        
        D5_75 ve D5_95 fonksiyonları doğru çalışmalı
        """
        dt = 0.01
        t = np.arange(0, 10, dt)
        acc = 0.1 * np.sin(2 * np.pi * t) * np.exp(-t/5)
        
        # Doğrudan hesaplama
        d1 = EarthquakeStats.calculate_significant_duration(acc, dt, 5.0, 75.0, 'g')
        
        # Kolaylık fonksiyonu
        d2 = EarthquakeStats.calculate_D5_75(acc, dt, 'g')
        
        # Aynı olmalı
        assert d1.duration == d2.duration
        assert d1.start_time == d2.start_time
        assert d1.end_time == d2.end_time
    
    def test_realistic_earthquake(self):
        """
        Test 10: Gerçekçi Deprem Simülasyonu
        
        Gerçek deprem kaydına benzer bir sinyal için mantıklı sonuçlar
        """
        dt = 0.01
        t = np.arange(0, 40, dt)
        
        # Gerçekçi deprem: Ana şok + artçı şoklar
        main_shock = 0.3 * np.exp(-((t - 5) ** 2) / 4) * np.sin(10 * np.pi * t)
        aftershock1 = 0.1 * np.exp(-((t - 15) ** 2) / 2) * np.sin(8 * np.pi * t)
        aftershock2 = 0.05 * np.exp(-((t - 25) ** 2) / 3) * np.sin(12 * np.pi * t)
        
        acc = main_shock + aftershock1 + aftershock2 + 0.01 * np.random.randn(len(t))
        
        d_95 = EarthquakeStats.calculate_D5_95(acc, dt, 'g')
        d_75 = EarthquakeStats.calculate_D5_75(acc, dt, 'g')
        
        # Mantıklı değerler
        assert 0 < d_75.duration < 40, f"D5-75 mantıksız: {d_75.duration}"
        assert 0 < d_95.duration < 40, f"D5-95 mantıksız: {d_95.duration}"
        assert d_75.duration <= d_95.duration
        
        # Başlangıç ve bitiş zamanları sıralı
        assert 0 <= d_95.start_time < d_95.end_time <= 40
    
    def test_cumulative_arias_intensity(self):
        """
        Test 11: Kümülatif Arias Intensity (PEER Algorithms §4)
        
        PEER Algorithms gereksinimi: Kümülatif I_A(t) hesaplama
        """
        dt = 0.01
        t = np.arange(0, 10, dt)
        acc = 0.1 * np.sin(2 * np.pi * t) * np.exp(-t/5)
        
        result = EarthquakeStats.calculate_arias_intensity_cumulative(acc, dt, 'g')
        
        # Temel kontroller
        assert result['IA_cumulative'].size == len(acc), "Boyut uyumsuz"
        assert result['IA_cumulative'][0] == 0.0, "İlk değer 0 olmalı"
        assert result['IA_total'] > 0, "Toplam pozitif olmalı"
        
        # Monotonluk kontrolü
        assert np.all(np.diff(result['IA_cumulative']) >= -1e-10), \
            "Kümülatif I_A monoton artan olmalı"
        
        # E_normalized kontrolü
        assert np.isclose(result['E_normalized'][-1], 1.0, rtol=1e-10), \
            "Normalize edilmiş enerji sonda 1.0 olmalı"
        
        # Toplam değer ile tek seferlik hesap uyumlu mu?
        ia_single = EarthquakeStats.calculate_arias_intensity(acc, dt, 'g')
        assert np.isclose(result['IA_total'], ia_single.arias_intensity, rtol=1e-10), \
            "Kümülatif toplam ile tek hesap uyumsuz"


class TestPEERComplianceReport:
    """PEER uygunluk raporu üretimi"""
    
    def test_full_compliance(self):
        """
        Tüm PEER testlerini çalıştırıp uygunluk raporu üret
        """
        print("\n" + "="*70)
        print("PEER Significant Duration Spesifikasyonu Uygunluk Raporu")
        print("="*70)
        
        tests = [
            ("Amplitüd Değişmezliği", "test_amplitude_invariance"),
            ("Süre Sıralaması (D5-75 ≤ D5-95)", "test_duration_ordering"),
            ("Birim Denkliği", "test_unit_equivalence"),
            ("Geçersiz dt Kontrolü", "test_invalid_dt"),
            ("Bozuk Kayıt Kontrolü", "test_invalid_record"),
            ("Monotonluk Garantisi", "test_monotonicity"),
            ("İki Bileşen MAX", "test_two_components_max"),
            ("İki Bileşen MEAN (PEER Algorithms §5)", "test_two_components_mean"),
            ("Kolaylık Fonksiyonları", "test_convenience_functions"),
            ("Gerçekçi Deprem", "test_realistic_earthquake"),
            ("Kümülatif Arias Intensity", "test_cumulative_arias_intensity"),
        ]
        
        passed = 0
        failed = 0
        
        for name, test_name in tests:
            try:
                # Test metodunu çalıştır
                test_obj = TestPEERSignificantDuration()
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
            print("🎉 TÜM TESTLER BAŞARILI - PEER UYUMLU!")
        
        assert failed == 0, f"{failed} test başarısız"


if __name__ == "__main__":
    # Tek başına çalıştırma
    import sys
    
    print("PEER Significant Duration Testleri")
    print("-" * 70)
    
    # Tüm testleri çalıştır
    pytest.main([__file__, "-v", "--tb=short"])

