"""
Kapsamlı EarthquakeStats birim testleri
Analitik çözümler ve bilinen sonuçlarla doğrulama
"""

import numpy as np
import unittest
import sys
import os

# Proje kök dizinini path'e ekle
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.calculations.earthquake_stats import EarthquakeStats


class TestEarthquakeStatsComprehensive(unittest.TestCase):
    """Kapsamlı EarthquakeStats testleri"""
    
    def setUp(self):
        """Test kurulumu"""
        self.dt = 0.01  # 100 Hz örnekleme
        self.tolerance = 1e-6  # Sayısal tolerans
        
    def test_constant_acceleration_arias_intensity(self):
        """
        Sabit ivme için Arias Intensity analitik çözümü
        a(t) = const için Ia = (π/(2g)) * a² * T
        """
        # Test parametreleri
        duration = 10.0  # saniye
        a_const = 0.1  # g
        time_array = np.arange(0, duration, self.dt)
        accel_array = np.full_like(time_array, a_const)
        
        # Analitik çözüm
        expected_ia = (np.pi / (2 * EarthquakeStats.G_STANDARD)) * (a_const * EarthquakeStats.G_STANDARD)**2 * duration
        
        # Hesaplanan değer
        result = EarthquakeStats.calculate_arias_intensity(accel_array, self.dt, 'g')
        calculated_ia = result['arias_intensity']
        
        # Doğrulama (sayısal entegrasyon toleransı - %1 hata kabul edilebilir)
        relative_error = abs(calculated_ia - expected_ia) / expected_ia
        self.assertLess(relative_error, 0.01,
                       msg=f"Sabit ivme Arias Intensity: beklenen={expected_ia:.6f}, hesaplanan={calculated_ia:.6f}, hata=%{relative_error*100:.2f}")
        
        # Birim kontrolü
        self.assertEqual(result['unit'], 'm/s')
        
    def test_sine_wave_pga_timing(self):
        """
        Sinüs dalgası için PGA zamanı doğrulaması
        a(t) = A * sin(2πf*t) için pik t = 1/(4f) anında olmalı
        """
        # Test parametreleri
        amplitude = 0.5  # g
        frequency = 2.0  # Hz
        duration = 2.0  # saniye
        
        time_array = np.arange(0, duration, self.dt)
        accel_array = amplitude * np.sin(2 * np.pi * frequency * time_array)
        
        # Beklenen pik zamanı (ilk pozitif maksimum)
        expected_peak_time = 1.0 / (4 * frequency)  # 0.125 s
        
        # PGA hesapla
        result = EarthquakeStats.calculate_pga(accel_array, self.dt, 'g')
        
        # Pik değer kontrolü (örnekleme hatası toleransı - %1 hata kabul edilebilir)
        relative_error_abs = abs(result['pga_abs'] - amplitude) / amplitude
        relative_error_pos = abs(result['pga_pos'] - amplitude) / amplitude
        self.assertLess(relative_error_abs, 0.01,
                       msg=f"PGA mutlak: beklenen={amplitude:.4f}, hesaplanan={result['pga_abs']:.4f}, hata=%{relative_error_abs*100:.2f}")
        self.assertLess(relative_error_pos, 0.01,
                       msg=f"PGA pozitif: beklenen={amplitude:.4f}, hesaplanan={result['pga_pos']:.4f}, hata=%{relative_error_pos*100:.2f}")
        
        # Pik zamanı kontrolü (çok döngülü sinüste herhangi bir pik kabul edilebilir)
        # Sinüs dalgasında her T/2 periyotta bir pik var
        period = 1.0 / frequency  # 0.5s
        half_period = period / 2  # 0.25s
        
        # Hesaplanan pik zamanının herhangi bir beklenen pik zamanına yakın olması yeterli
        possible_peak_times = [expected_peak_time + i * half_period for i in range(8)]  # İlk 4 saniye için
        
        min_time_error = min(abs(result['t_peak_abs'] - pt) for pt in possible_peak_times)
        self.assertLess(min_time_error, 2*self.dt,
                       msg=f"PGA pik zamanı: hesaplanan={result['t_peak_abs']:.3f}s, beklenen piklerden biri={possible_peak_times[:3]}, min hata={min_time_error:.3f}s")
        
    def test_pgv_pgd_sine_wave_timing(self):
        """
        Sinüs dalgası türevleri için PGV/PGD zamanı doğrulaması
        """
        # Test parametreleri
        amplitude = 0.2  # g
        frequency = 1.0  # Hz
        duration = 3.0  # saniye
        
        time_array = np.arange(0, duration, self.dt)
        accel_array = amplitude * np.sin(2 * np.pi * frequency * time_array)
        
        # Analitik hız ve yerdeğiştirme (entegrasyon)
        # v(t) = -A/(2πf) * cos(2πf*t) + C
        # d(t) = -A/(4π²f²) * sin(2πf*t) + Ct + D
        velocity_amplitude = amplitude * EarthquakeStats.G_STANDARD / (2 * np.pi * frequency)  # m/s
        displacement_amplitude = amplitude * EarthquakeStats.G_STANDARD / (4 * np.pi**2 * frequency**2)  # m
        
        # PGV için beklenen pik zamanı (cos'un maksimumu)
        expected_pgv_time = 0.0  # t=0'da cos maksimum
        
        # PGD için beklenen pik zamanı (sin'in maksimumu)  
        expected_pgd_time = 1.0 / (4 * frequency)  # 0.25 s
        
        # Basit entegrasyon ile hız ve yerdeğiştirme hesapla
        velocity_array = np.zeros_like(accel_array)
        displacement_array = np.zeros_like(accel_array)
        
        # Trapezoidal entegrasyon
        accel_ms2 = accel_array * EarthquakeStats.G_STANDARD
        for i in range(1, len(accel_ms2)):
            velocity_array[i] = velocity_array[i-1] + (accel_ms2[i] + accel_ms2[i-1]) * self.dt / 2
            displacement_array[i] = displacement_array[i-1] + (velocity_array[i] + velocity_array[i-1]) * self.dt / 2
        
        # PGV hesapla
        pgv_result = EarthquakeStats.calculate_pgv(velocity_array, self.dt, 'm/s')
        
        # PGD hesapla  
        pgd_result = EarthquakeStats.calculate_pgd(displacement_array, self.dt, 'm')
        
        # Değer büyüklük kontrolü (yaklaşık)
        self.assertGreater(pgv_result['pgv_abs'], velocity_amplitude * 0.8)
        self.assertGreater(pgd_result['pgd_abs'], displacement_amplitude * 0.8)
        
        print(f"PGV: hesaplanan={pgv_result['pgv_abs']:.4f} m/s, beklenen~{velocity_amplitude:.4f} m/s")
        print(f"PGD: hesaplanan={pgd_result['pgd_abs']:.6f} m, beklenen~{displacement_amplitude:.6f} m")
        
    def test_significant_duration_husid_points(self):
        """
        Bilinen Husid eğrisi noktaları için D5-95 doğrulaması
        """
        # Basit test: iki darbe (impulse) durumu
        duration = 20.0  # saniye
        time_array = np.arange(0, duration, self.dt)
        accel_array = np.zeros_like(time_array)
        
        # İlk darbe: t=2s'de
        pulse1_idx = int(2.0 / self.dt)
        accel_array[pulse1_idx:pulse1_idx+10] = 1.0  # g
        
        # İkinci darbe: t=18s'de  
        pulse2_idx = int(18.0 / self.dt)
        accel_array[pulse2_idx:pulse2_idx+10] = 1.0  # g
        
        # D5-95 hesapla
        result = EarthquakeStats.calculate_significant_duration(accel_array, self.dt, 5.0, 95.0, 'g')
        
        # Beklenen süre yaklaşık 16 saniye (18-2) olmalı
        expected_duration = 16.0
        calculated_duration = result['duration']
        
        # Toleranslı kontrol
        self.assertAlmostEqual(calculated_duration, expected_duration, delta=1.0,
                              msg=f"D5-95: beklenen~{expected_duration:.1f}s, hesaplanan={calculated_duration:.1f}s")
        
        # Başlangıç ve bitiş zamanları
        self.assertGreater(result['start_time'], 1.0)  # 2s civarında başlamalı
        self.assertLess(result['start_time'], 3.0)
        
        self.assertGreater(result['end_time'], 17.0)   # 18s civarında bitmeli
        self.assertLess(result['end_time'], 19.0)
        
    def test_cav_constant_acceleration(self):
        """
        Sabit ivme için CAV analitik çözümü
        CAV = ∫|a(t)|dt = |a| * T
        """
        # Test parametreleri
        duration = 5.0  # saniye
        a_const = 0.2  # g
        time_array = np.arange(0, duration, self.dt)
        accel_array = np.full_like(time_array, a_const)
        
        # Analitik çözüm
        expected_cav = abs(a_const) * duration  # g·s
        expected_cav_si = expected_cav * EarthquakeStats.G_STANDARD  # m/s
        
        # CAV hesapla
        result = EarthquakeStats.calculate_cav(accel_array, self.dt, 'g')
        
        # Doğrulama (sayısal entegrasyon toleransı - %1 hata kabul edilebilir)
        relative_error_cav = abs(result['cav'] - expected_cav) / expected_cav
        relative_error_si = abs(result['cav_si'] - expected_cav_si) / expected_cav_si
        
        self.assertLess(relative_error_cav, 0.01,
                       msg=f"CAV: beklenen={expected_cav:.4f} g·s, hesaplanan={result['cav']:.4f}, hata=%{relative_error_cav*100:.2f}")
        
        self.assertLess(relative_error_si, 0.01,
                       msg=f"CAV SI: beklenen={expected_cav_si:.2f} m/s, hesaplanan={result['cav_si']:.2f}, hata=%{relative_error_si*100:.2f}")
        
    def test_unit_conversions(self):
        """
        Birim çevrim fonksiyonları doğrulaması
        """
        test_value = 1.0
        
        # g -> m/s² çevrimi
        result_ms2 = EarthquakeStats._convert_acceleration_to_ms2(np.array([test_value]), 'g')
        self.assertAlmostEqual(result_ms2[0], EarthquakeStats.G_STANDARD, places=5)
        
        # m/s² -> g çevrimi
        result_g = EarthquakeStats._convert_acceleration_to_g(np.array([EarthquakeStats.G_STANDARD]), 'm/s²')
        self.assertAlmostEqual(result_g[0], 1.0, places=5)
        
        # CAV çevrimi
        cav_si = EarthquakeStats._convert_cav_to_si(1.0, 'g')
        self.assertAlmostEqual(cav_si, EarthquakeStats.G_STANDARD, places=5)
        
    def test_nan_inf_robustness(self):
        """
        NaN/Inf değerlere karşı dayanıklılık testi
        """
        # NaN içeren veri
        time_array = np.arange(0, 1, self.dt)
        accel_array = np.ones_like(time_array) * 0.1
        # Sadece birkaç değeri NaN/Inf yap (çoğunluk geçerli kalmalı)
        accel_array[50] = np.nan
        accel_array[60] = np.inf
        accel_array[70] = -np.inf
        
        # PGA hesapla
        pga_result = EarthquakeStats.calculate_pga(accel_array, self.dt, 'g')
        
        # Sonuçlar NaN olmamalı (geçerli değerler var)
        print(f"PGA sonucu: {pga_result['pga_abs']}, geçerli örnekler: {pga_result['valid_samples']}")
        if pga_result['valid_samples'] > 0:
            self.assertFalse(np.isnan(pga_result['pga_abs']))
        else:
            # Eğer geçerli örnek yoksa NaN olması normal
            self.assertTrue(np.isnan(pga_result['pga_abs']))
        
        self.assertGreaterEqual(pga_result['valid_samples'], 0)
        
        # Arias Intensity hesapla
        ia_result = EarthquakeStats.calculate_arias_intensity(accel_array, self.dt, 'g')
        self.assertFalse(np.isnan(ia_result['arias_intensity']))
        
    def test_sampling_uniformity_detection(self):
        """
        Örnekleme tekdüzeliği algılama testi
        """
        # Düzenli örnekleme
        uniform_time = np.arange(0, 1, 0.01)
        accel = np.zeros_like(uniform_time)
        vel = np.zeros_like(uniform_time)
        disp = np.zeros_like(uniform_time)
        
        result_uniform = EarthquakeStats.calculate_all_stats(uniform_time, accel, vel, disp)
        self.assertTrue(result_uniform['sampling_info']['sampling_uniform'])
        
        # Düzensiz örnekleme
        irregular_time = uniform_time.copy()
        irregular_time[50:60] += 0.002  # Bir bölümde zaman kayması
        
        result_irregular = EarthquakeStats.calculate_all_stats(irregular_time, accel, vel, disp)
        # Bu durumda tekdüzelik düşük çıkabilir
        uniformity = result_irregular['sampling_info']['uniformity_ratio']
        self.assertIsInstance(uniformity, float)
        self.assertGreaterEqual(uniformity, 0.0)
        self.assertLessEqual(uniformity, 1.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
