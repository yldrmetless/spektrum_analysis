"""
Response Spectrum modülü için test dosyası
"""

import unittest
import numpy as np
import os
import tempfile
from pathlib import Path

# Test edilecek modülleri import et
try:
    from src.calculations.response_spectrum import (
        SpectrumSettings,
        SpectrumCurves,
        compute_elastic_response_spectrum,
        export_spectra_to_csv,
        plot_spectra,
        read_timeseries_auto,
        _baseline_correct,
        _resample_if_needed,
        _newmark_peaks
    )
    RESPONSE_SPECTRUM_AVAILABLE = True
except ImportError:
    RESPONSE_SPECTRUM_AVAILABLE = False

class TestResponseSpectrum(unittest.TestCase):
    """Response Spectrum hesaplamalarını test eder"""
    
    def setUp(self):
        """Test için gerekli verileri hazırlar"""
        if not RESPONSE_SPECTRUM_AVAILABLE:
            self.skipTest("response_spectrum modülü bulunamadı")
        
        # Basit sinüzoidal deprem kaydı oluştur
        self.dt = 0.01  # 100 Hz
        self.duration = 20.0  # 20 saniye
        self.time = np.arange(0, self.duration, self.dt)
        
        # Ricker wavelet (Mexican hat) benzeri sinyal
        fc = 2.0  # Merkez frekansı 2 Hz
        t_shift = self.duration / 4
        self.acceleration = (1 - 2 * np.pi**2 * fc**2 * (self.time - t_shift)**2) * \
                           np.exp(-np.pi**2 * fc**2 * (self.time - t_shift)**2)
        
        # Biraz gürültü ekle
        np.random.seed(42)  # Tekrarlanabilir sonuçlar için
        noise = 0.05 * np.random.randn(len(self.acceleration))
        self.acceleration += noise
        
        # Peak'i yaklaşık 0.3g yap
        self.acceleration = self.acceleration * 0.3 / np.max(np.abs(self.acceleration))
    
    def test_spectrum_settings(self):
        """SpectrumSettings dataclass'ını test eder"""
        # Varsayılan ayarlar
        settings = SpectrumSettings()
        self.assertEqual(settings.damping_list, (5.0,))
        self.assertEqual(settings.Tmin, 0.01)
        self.assertEqual(settings.Tmax, 10.0)
        self.assertEqual(settings.nT, 500)
        self.assertTrue(settings.logspace)
        self.assertEqual(settings.accel_unit, "g")
        
        # Özel ayarlar
        custom_settings = SpectrumSettings(
            damping_list=[2.0, 5.0, 10.0],
            Tmin=0.02,
            Tmax=5.0,
            nT=200,
            accel_unit="m/s²"
        )
        self.assertEqual(custom_settings.damping_list, [2.0, 5.0, 10.0])
        self.assertEqual(custom_settings.Tmin, 0.02)
        self.assertEqual(custom_settings.accel_unit, "m/s²")
    
    def test_baseline_correct(self):
        """Baseline düzeltme fonksiyonunu test eder"""
        # Test verisi - trend içeren
        n = 1000
        t = np.linspace(0, 10, n)
        trend = 0.1 * t  # Lineer trend
        signal = np.sin(2 * np.pi * t) + trend
        dt = t[1] - t[0]
        
        # Trend yok
        corrected_none = _baseline_correct(signal, dt, "none")
        np.testing.assert_array_equal(corrected_none, signal)
        
        # Ortalama çıkar
        corrected_demean = _baseline_correct(signal, dt, "demean")
        self.assertAlmostEqual(np.mean(corrected_demean), 0.0, places=10)
        
        # Lineer trend çıkar
        corrected_linear = _baseline_correct(signal, dt, "linear")
        # Düzeltilmiş sinyal yaklaşık sinüs olmalı
        expected = np.sin(2 * np.pi * t)
        rms_error = np.sqrt(np.mean((corrected_linear - expected)**2))
        self.assertLess(rms_error, 0.1)
    
    def test_resample_if_needed(self):
        """Alt-örnekleme fonksiyonunu test eder"""
        t = np.linspace(0, 1, 1000)  # dt = 0.001
        a = np.sin(2 * np.pi * 5 * t)  # 5 Hz sinyal
        
        # Limit yok
        t_new, a_new, dt_new, changed = _resample_if_needed(t, a, 0.1, None)
        self.assertFalse(changed)
        np.testing.assert_array_equal(t_new, t)
        
        # dt/T limiti aşılıyor
        max_dt_over_T = 0.01  # T_min = 0.1 -> dt <= 0.001
        t_new, a_new, dt_new, changed = _resample_if_needed(t, a, 0.1, max_dt_over_T)
        self.assertTrue(changed)
        self.assertLessEqual(dt_new, 0.001)
    
    def test_newmark_peaks(self):
        """Newmark-β tepe değer hesaplamasını test eder"""
        # Basit impuls
        dt = 0.01
        n = 1000
        acc = np.zeros(n)
        acc[100:110] = 1.0  # 0.1 saniye süren 1 m/s² impuls
        
        # SDOF parametreleri
        T = 1.0  # 1 saniye periyot
        omega = 2 * np.pi / T
        zeta = 0.05  # %5 sönüm
        
        Sd_max, Sv_p_max, Sa_p_max, Sa_abs_max = _newmark_peaks(acc, dt, omega, zeta)
        
        # Sonuçlar pozitif olmalı
        self.assertGreater(Sd_max, 0)
        self.assertGreater(Sv_p_max, 0) 
        self.assertGreater(Sa_p_max, 0)
        self.assertGreater(Sa_abs_max, 0)
        
        # Pseudo ilişkileri kontrol et
        self.assertAlmostEqual(Sv_p_max, omega * Sd_max, places=3)
        self.assertAlmostEqual(Sa_p_max, omega**2 * Sd_max, places=2)
    
    def test_compute_elastic_response_spectrum(self):
        """Ana ERS hesaplama fonksiyonunu test eder"""
        settings = SpectrumSettings(
            damping_list=[5.0],
            Tmin=0.1,
            Tmax=2.0,
            nT=50,
            accel_unit="g"
        )
        
        results = compute_elastic_response_spectrum(self.time, self.acceleration, settings)
        
        # Sonuç yapısını kontrol et
        self.assertIn(5.0, results)
        curves = results[5.0]
        self.assertIsInstance(curves, SpectrumCurves)
        
        # Veri boyutları
        self.assertEqual(len(curves.T), 50)
        self.assertEqual(len(curves.Sd), 50)
        self.assertEqual(len(curves.Sv_p), 50)
        self.assertEqual(len(curves.Sa_p), 50)
        self.assertEqual(len(curves.Sa_p_g), 50)
        
        # Periyot aralığı
        self.assertAlmostEqual(curves.T[0], 0.1, places=2)
        self.assertAlmostEqual(curves.T[-1], 2.0, places=2)
        
        # Pozitif değerler
        self.assertTrue(np.all(curves.Sd >= 0))
        self.assertTrue(np.all(curves.Sv_p >= 0))
        self.assertTrue(np.all(curves.Sa_p >= 0))
        self.assertTrue(np.all(curves.Sa_p_g >= 0))
        
        # Pseudo ilişkileri (yaklaşık)
        omega = 2 * np.pi / curves.T
        np.testing.assert_allclose(curves.Sv_p, omega * curves.Sd, rtol=0.01)
        np.testing.assert_allclose(curves.Sa_p, omega**2 * curves.Sd, rtol=0.01)
        
        # g dönüşümü
        from src.calculations.earthquake_stats import EarthquakeStats
        expected_Sa_p_g = curves.Sa_p / EarthquakeStats.G_STANDARD
        np.testing.assert_allclose(curves.Sa_p_g, expected_Sa_p_g, rtol=1e-10)
    
    def test_multiple_damping(self):
        """Çoklu sönüm değerleri ile test"""
        settings = SpectrumSettings(
            damping_list=[2.0, 5.0, 10.0],
            Tmin=0.1,
            Tmax=1.0,
            nT=20
        )
        
        results = compute_elastic_response_spectrum(self.time, self.acceleration, settings)
        
        # Tüm sönüm değerleri mevcut
        self.assertEqual(set(results.keys()), {2.0, 5.0, 10.0})
        
        # Sönüm arttıkça spektrum değerleri genelde azalır
        Sa_2 = results[2.0].Sa_p_g
        Sa_5 = results[5.0].Sa_p_g
        Sa_10 = results[10.0].Sa_p_g
        
        # En azından maksimum değerler için bu geçerli olmalı
        self.assertGreater(np.max(Sa_2), np.max(Sa_10))
    
    def test_export_csv(self):
        """CSV dışa aktarma fonksiyonunu test eder"""
        settings = SpectrumSettings(
            damping_list=[5.0, 10.0],
            Tmin=0.1,
            Tmax=1.0,
            nT=10
        )
        
        results = compute_elastic_response_spectrum(self.time, self.acceleration, settings)
        
        # Geçici dosya oluştur
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            # Export et
            output_path = export_spectra_to_csv(results, temp_path)
            self.assertEqual(output_path, temp_path)
            self.assertTrue(os.path.exists(temp_path))
            
            # Dosya içeriğini kontrol et
            with open(temp_path, 'r') as f:
                lines = f.readlines()
            
            # Header kontrolü
            header = lines[0].strip()
            self.assertIn('T[s]', header)
            self.assertIn('Sd_5.0%[m]', header)
            self.assertIn('Sa_p_10.0%[g]', header)
            
            # Veri satırı sayısı
            self.assertEqual(len(lines), 11)  # 1 header + 10 data rows
            
        finally:
            # Geçici dosyayı sil
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_plot_spectra(self):
        """Grafik çizim fonksiyonunu test eder"""
        settings = SpectrumSettings(
            damping_list=[5.0],
            Tmin=0.1,
            Tmax=1.0,
            nT=20
        )
        
        results = compute_elastic_response_spectrum(self.time, self.acceleration, settings)
        
        # Geçici PNG dosyası
        with tempfile.NamedTemporaryFile(mode='w', suffix='.png', delete=False) as f:
            temp_path = f.name
        
        try:
            # PNG oluştur
            output_path = plot_spectra(
                results,
                ytype="sa",
                xaxis="period", 
                title="Test ERS",
                outfile=temp_path
            )
            
            self.assertEqual(output_path, temp_path)
            self.assertTrue(os.path.exists(temp_path))
            
            # Dosya boyutu kontrolü (boş değil)
            self.assertGreater(os.path.getsize(temp_path), 1000)
            
        finally:
            # Geçici dosyayı sil
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_read_timeseries_csv(self):
        """CSV dosya okuma fonksiyonunu test eder"""
        # Test CSV oluştur
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
            # İki sütunlu: zaman, ivme
            for i, (t, a) in enumerate(zip(self.time[:100], self.acceleration[:100])):
                f.write(f"{t:.6f},{a:.6f}\n")
        
        try:
            time_read, accel_read, dt_read, unit_guess = read_timeseries_auto(temp_path)
            
            # Veri kontrolü
            np.testing.assert_allclose(time_read, self.time[:100], rtol=1e-5, atol=1e-8)
            np.testing.assert_allclose(accel_read, self.acceleration[:100], rtol=1e-5, atol=1e-6)
            self.assertAlmostEqual(dt_read, self.dt, places=5)
            self.assertEqual(unit_guess, "g")
            
        finally:
            os.unlink(temp_path)
    
    def test_read_timeseries_single_column(self):
        """Tek sütunlu dosya okuma fonksiyonunu test eder"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = f.name
            # Sadece ivme değerleri
            for a in self.acceleration[:50]:
                f.write(f"{a:.6f}\n")
        
        try:
            time_read, accel_read, dt_read, unit_guess = read_timeseries_auto(
                temp_path, dt_hint=self.dt
            )
            
            # Veri kontrolü
            expected_time = np.arange(50) * self.dt
            np.testing.assert_allclose(time_read, expected_time, rtol=1e-10, atol=1e-12)
            np.testing.assert_allclose(accel_read, self.acceleration[:50], rtol=1e-5, atol=1e-6)
            self.assertEqual(dt_read, self.dt)
            
        finally:
            os.unlink(temp_path)
    
    def test_convergence_with_dt(self):
        """dt azaltıldığında sonuçların yakınsadığını test eder"""
        # Kaba dt ile hesapla
        time_coarse = self.time[::2]  # dt = 0.02
        accel_coarse = self.acceleration[::2]
        
        settings = SpectrumSettings(
            damping_list=[5.0],
            Tmin=0.2,
            Tmax=1.0,
            nT=20,
            accel_unit="g"
        )
        
        # Kaba ve ince çözümler
        results_coarse = compute_elastic_response_spectrum(time_coarse, accel_coarse, settings)
        results_fine = compute_elastic_response_spectrum(self.time, self.acceleration, settings)
        
        # Spektrum eğrileri yakın olmalı (<%10 fark)
        Sa_coarse = results_coarse[5.0].Sa_p_g
        Sa_fine = results_fine[5.0].Sa_p_g
        
        relative_error = np.abs(Sa_coarse - Sa_fine) / (Sa_fine + 1e-6)
        max_error = np.max(relative_error)
        
        # Çoğu nokta için %20'den az fark olmalı (dt etkisi)
        self.assertLess(np.percentile(relative_error, 90), 0.2)

class TestResponseSpectrumIntegration(unittest.TestCase):
    """Response Spectrum entegrasyon testleri"""
    
    def setUp(self):
        """Test için gerekli verileri hazırlar"""
        if not RESPONSE_SPECTRUM_AVAILABLE:
            self.skipTest("response_spectrum modülü bulunamadı")
    
    def test_earthquake_stats_integration(self):
        """EarthquakeStats ile entegrasyon testi"""
        from src.calculations.earthquake_stats import EarthquakeStats
        
        # Test verisi
        dt = 0.01
        time = np.arange(0, 10, dt)
        acceleration = 0.2 * np.sin(2 * np.pi * 2 * time) * np.exp(-0.1 * time)
        
        # Birim dönüşümlerini test et
        accel_ms2 = EarthquakeStats.convert_acceleration_to_ms2(acceleration, 'g')
        accel_g = EarthquakeStats.convert_acceleration_to_g(accel_ms2, 'm/s²')
        
        # Geri dönüşüm doğruluğu
        np.testing.assert_allclose(acceleration, accel_g, rtol=1e-10)
        
        # ERS hesaplama
        settings = SpectrumSettings(
            damping_list=[5.0],
            Tmin=0.1,
            Tmax=2.0,
            nT=30,
            accel_unit="g"
        )
        
        results = compute_elastic_response_spectrum(time, acceleration, settings)
        curves = results[5.0]
        
        # Sonuçlar makul aralıkta olmalı
        self.assertGreater(np.max(curves.Sa_p_g), 0.01)  # En az 0.01g
        self.assertLess(np.max(curves.Sa_p_g), 2.0)      # En fazla 2g (makul)

if __name__ == '__main__':
    unittest.main(verbosity=2)
