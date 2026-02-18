"""
TBDY Spektrum Hesaplamaları için Kapsamlı Birim Testleri
------------------------------------------------------

Bu test dosyası spectrum.py modülündeki hesaplamaları doğrular:
1. Yatay spektrum kritik noktalarında değer kontrolü
2. Düşey spektrum kritik noktalarında değer kontrolü  
3. Yerdeğiştirme spektrumu için el hesabı karşılaştırması
4. Hatalı girdiler için exception testleri
5. NaN kırpma özelliği testleri
"""

import unittest
import numpy as np
import pandas as pd
from src.calculations.spectrum import SpectrumCalculator
from src.config.constants import DEFAULT_TL, GRAVITY_CM


class TestSpectrumCalculatorComprehensive(unittest.TestCase):
    
    def setUp(self):
        """Test öncesi hazırlık"""
        self.calculator = SpectrumCalculator()
        
        # Test parametreleri (tipik değerler)
        self.SDS = 1.2  # g
        self.SD1 = 0.8  # g
        self.TL = 6.0   # s
        
        # Kritik periyotlar
        self.TA = 0.2 * self.SD1 / self.SDS  # = 0.133 s
        self.TB = self.SD1 / self.SDS         # = 0.667 s
        self.T_AD = self.TA / 3.0             # = 0.044 s  
        self.T_BD = self.TB / 3.0             # = 0.222 s
        self.T_LD = self.TL / 2.0             # = 3.0 s
        
        # Tolerans değeri (numerical precision için)
        self.tolerance = 1e-10
    
    # =========================================================================
    # YATAY SPEKTRUM TESTLERİ
    # =========================================================================
    
    def test_horizontal_spectrum_critical_points(self):
        """Yatay spektrumun kritik noktalarındaki değerleri test eder"""
        
        # Test periyotları: kritik noktalar
        T_test = np.array([0.0, self.TA, self.TB, self.TL, self.TL + 1.0])
        
        sae_T, TA_calc, TB_calc = self.calculator.calculate_horizontal_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # Kritik periyotların doğruluğu
        self.assertAlmostEqual(TA_calc, self.TA, places=10)
        self.assertAlmostEqual(TB_calc, self.TB, places=10)
        
        # Beklenen değerler (TBDY-2018 Denklem 2.2)
        expected_values = np.array([
            0.4 * self.SDS,                           # T = 0: 0.4 * SDS
            self.SDS,                                 # T = TA: SDS  
            self.SDS,                                 # T = TB: SDS
            self.SD1 / self.TL,                       # T = TL: SD1/TL
            self.SD1 * self.TL / ((self.TL + 1.0)**2) # T > TL: SD1*TL/T²
        ])
        
        # Toleranslı karşılaştırma
        np.testing.assert_allclose(sae_T, expected_values, rtol=self.tolerance)
    
    def test_horizontal_spectrum_intermediate_points(self):
        """Yatay spektrumun ara değerlerini test eder"""
        
        # TA < T < TB aralığında test
        T_middle = (self.TA + self.TB) / 2.0
        T_test = np.array([T_middle])
        
        sae_T, _, _ = self.calculator.calculate_horizontal_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # Bu aralıkta değer SDS olmalı
        expected = self.SDS
        self.assertAlmostEqual(sae_T[0], expected, places=10)
        
        # 0 < T < TA aralığında test
        T_early = self.TA / 2.0
        T_test = np.array([T_early])
        
        sae_T, _, _ = self.calculator.calculate_horizontal_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # Bu aralıkta: (0.4 + 0.6 * T/TA) * SDS
        expected = (0.4 + 0.6 * T_early / self.TA) * self.SDS
        self.assertAlmostEqual(sae_T[0], expected, places=10)
    
    # =========================================================================
    # DÜŞEY SPEKTRUM TESTLERİ
    # =========================================================================
    
    def test_vertical_spectrum_critical_points(self):
        """Düşey spektrumun kritik noktalarındaki değerleri test eder"""
        
        # Test periyotları
        T_test = np.array([0.0, self.T_AD, self.T_BD, self.T_LD, self.T_LD + 1.0])
        
        saeD_T, T_AD_calc, T_BD_calc = self.calculator.calculate_vertical_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # Kritik periyotların doğruluğu
        self.assertAlmostEqual(T_AD_calc, self.T_AD, places=10)
        self.assertAlmostEqual(T_BD_calc, self.T_BD, places=10)
        
        # Beklenen değerler (TBDY-2018 Denklem 2.5)
        expected_values = np.array([
            0.32 * self.SDS,                          # T = 0: 0.32 * SDS
            0.8 * self.SDS,                           # T = T_AD: 0.8 * SDS
            0.8 * self.SDS,                           # T = T_BD: 0.8 * SDS  
            0.8 * self.SDS * (self.T_BD / self.T_LD), # T = T_LD: 0.8*SDS*(T_BD/T_LD)
            np.nan                                     # T > T_LD: NaN
        ])
        
        # NaN olmayan değerler için karşılaştırma
        valid_mask = ~np.isnan(expected_values)
        np.testing.assert_allclose(
            saeD_T[valid_mask], 
            expected_values[valid_mask], 
            rtol=self.tolerance
        )
        
        # T > T_LD için NaN kontrolü
        self.assertTrue(np.isnan(saeD_T[-1]))
    
    def test_vertical_spectrum_intermediate_points(self):
        """Düşey spektrumun ara değerlerini test eder"""
        
        # T_AD < T < T_BD aralığında test
        T_middle = (self.T_AD + self.T_BD) / 2.0
        T_test = np.array([T_middle])
        
        saeD_T, _, _ = self.calculator.calculate_vertical_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # Bu aralıkta değer 0.8*SDS olmalı
        expected = 0.8 * self.SDS
        self.assertAlmostEqual(saeD_T[0], expected, places=10)
        
        # 0 < T < T_AD aralığında test
        T_early = self.T_AD / 2.0
        T_test = np.array([T_early])
        
        saeD_T, _, _ = self.calculator.calculate_vertical_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # Bu aralıkta: (0.32 + 0.48 * T/T_AD) * SDS
        expected = (0.32 + 0.48 * T_early / self.T_AD) * self.SDS
        self.assertAlmostEqual(saeD_T[0], expected, places=10)
    
    # =========================================================================
    # YERDEĞİŞTİRME SPEKTRUMU TESTLERİ (EL HESABI)
    # =========================================================================
    
    def test_displacement_spectrum_manual_calculation(self):
        """Yerdeğiştirme spektrumu için el hesabı karşılaştırması"""
        
        # Test periyotları (çeşitli aralıklardan)
        T_test = np.array([0.5, 1.0, 2.0, 4.0])  # s
        
        sde_T, _, _ = self.calculator.calculate_displacement_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # El hesabı: Denklem 2.4 -> Sde(T) = Sae(T) * g * (T/2π)²
        # Önce yatay spektrumu hesapla
        sae_T, _, _ = self.calculator.calculate_horizontal_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # Manuel hesaplama
        expected_sde = sae_T * GRAVITY_CM * (T_test / (2 * np.pi))**2
        
        # Toleranslı karşılaştırma
        np.testing.assert_allclose(sde_T, expected_sde, rtol=self.tolerance)
    
    def test_displacement_spectrum_specific_values(self):
        """Belirli T değerleri için detaylı el hesabı"""
        
        # T = 1.0 s için test (TB < T < TL aralığında)
        T = 1.0
        T_test = np.array([T])
        
        sde_T, _, _ = self.calculator.calculate_displacement_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # Manuel hesaplama:
        # 1) T = 1.0 > TB = 0.667, T < TL = 6.0 -> Sae = SD1/T = 0.8/1.0 = 0.8 g
        # 2) Sde = Sae * g * (T/2π)² = 0.8 * 981 * (1.0/6.283)² ≈ 19.87 cm
        expected_sae = self.SD1 / T  # = 0.8 g
        expected_sde = expected_sae * GRAVITY_CM * (T / (2 * np.pi))**2
        
        self.assertAlmostEqual(sde_T[0], expected_sde, places=3)  # cm hassasiyeti
    
    def test_displacement_spectrum_zero_period(self):
        """T=0 için yerdeğiştirme spektrumu testi"""
        
        T_test = np.array([0.0])
        sde_T, _, _ = self.calculator.calculate_displacement_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # T=0'da yerdeğiştirme 0 olmalı
        self.assertEqual(sde_T[0], 0.0)
    
    # =========================================================================
    # HATALI GİRDİLER İÇİN EXCEPTION TESTLERİ
    # =========================================================================
    
    def test_invalid_sds_zero(self):
        """SDS=0 için division by zero testi"""
        
        T_test = np.array([0.1, 1.0])
        SDS_invalid = 0.0
        
        # SDS=0 durumunda TA ve TB hesaplanamaz, ancak kod bunu handle ediyor
        sae_T, TA, TB = self.calculator.calculate_horizontal_spectrum(
            T_test, SDS_invalid, self.SD1, self.TL
        )
        
        # TA ve TB sıfır olmalı
        self.assertEqual(TA, 0.0)
        self.assertEqual(TB, 0.0)
        
        # SDS=0 durumunda TA=TB=0 olur, bu yüzden T=0.1 > TB koşulu sağlanır
        # Üçüncü bölge aktif olur: SD1/T = 0.8/0.1 = 8.0
        self.assertAlmostEqual(sae_T[0], self.SD1 / 0.1, places=10)
        # İkinci değer de SD1/T formülünden gelir (T=1.0 için SD1/1.0 = 0.8)
        self.assertAlmostEqual(sae_T[1], self.SD1 / 1.0, places=10)
    
    def test_negative_parameters(self):
        """Negatif parametreler için test"""
        
        T_test = np.array([1.0])
        
        # Negatif SDS testi - artık ValueError bekliyoruz
        with self.assertRaises(ValueError):
            self.calculator.calculate_horizontal_spectrum(T_test, -1.0, self.SD1, self.TL)
            
        # Negatif SD1 testi
        with self.assertRaises(ValueError):
            self.calculator.calculate_horizontal_spectrum(T_test, self.SDS, -1.0, self.TL)
            
        # Negatif/sıfır TL testi
        with self.assertRaises(ValueError):
            self.calculator.calculate_horizontal_spectrum(T_test, self.SDS, self.SD1, -1.0)
            
        with self.assertRaises(ValueError):
            self.calculator.calculate_horizontal_spectrum(T_test, self.SDS, self.SD1, 0.0)
    
    def test_invalid_tl_zero(self):
        """TL=0 için test - artık ValueError beklenir"""
        
        T_test = np.array([1.0, 10.0])
        
        # TL=0 durumu artık ValueError fırlatır
        with self.assertRaises(ValueError):
            self.calculator.calculate_horizontal_spectrum(T_test, self.SDS, self.SD1, 0.0)
    
    def test_period_array_negative_values(self):
        """Negatif periyot değerleri için test"""
        
        T_test = np.array([-1.0, 0.0, 1.0])
        
        sae_T, _, _ = self.calculator.calculate_horizontal_spectrum(
            T_test, self.SDS, self.SD1, self.TL
        )
        
        # Negatif periyot fiziksel olarak anlamsız, ancak matematik çalışmalı
        # İlk koşul T <= TA kontrol edilir
        self.assertIsNotNone(sae_T[0])  # NaN veya sayısal değer
    
    # =========================================================================
    # NaN KIRPMA ÖZELLİĞİ TESTLERİ
    # =========================================================================
    
    def test_vertical_nan_handling(self):
        """Düşey spektrumda NaN değerlerin doğru işlendiğini test eder"""
        
        # Düşey spektrum hesaplama
        result = self.calculator.calculate_all_spectra(
            self.SDS, self.SD1, self.TL,
            include_horizontal=False,
            include_vertical=True,
            include_displacement=False
        )
        
        # Düşey spektrumda NaN değerler olmalı (T > T_LD için)
        vertical_data = result['dataframe']['Düşey Spektral İvme (g)'].values
        self.assertTrue(np.any(np.isnan(vertical_data)))
        
        # NaN değerler sadece büyük periyotlarda olmalı
        period_data = result['dataframe'].index.values
        T_LD = self.TL / 2.0  # = 3.0 s
        
        # T_LD'den küçük değerlerde NaN olmamalı
        small_T_mask = period_data <= T_LD
        small_T_values = vertical_data[small_T_mask]
        self.assertFalse(np.any(np.isnan(small_T_values)))
        
        # T_LD'den büyük değerlerde NaN olmalı
        large_T_mask = period_data > T_LD
        if np.any(large_T_mask):
            large_T_values = vertical_data[large_T_mask]
            self.assertTrue(np.all(np.isnan(large_T_values)))
    
    # =========================================================================
    # PERİYOT DİZİSİ OLUŞTURMA TESTLERİ
    # =========================================================================
    
    def test_period_array_generation(self):
        """Periyot dizisi oluşturma testi"""
        
        T_array = self.calculator.generate_period_array_optimized(
            self.SDS, self.SD1, self.TL
        )
        
        # Kritik noktalar dahil olmalı
        critical_points = [self.TA, self.TB, self.T_AD, self.T_BD, self.T_LD, 1.0, self.TL]
        
        for point in critical_points:
            # Toleranslı kontrol (tam eşitlik olmayabilir)
            min_distance = np.min(np.abs(T_array - point))
            self.assertLess(min_distance, 1e-6, f"Kritik nokta {point} dizide bulunamadı")
        
        # Dizi artan sırada olmalı
        self.assertTrue(np.all(np.diff(T_array) >= 0))
        
        # Pozitif değerler olmalı (T=0 ayrıca eklenir, bu yüzden > 0 kontrolü)
        self.assertTrue(np.all(T_array > 0))
    
    # =========================================================================
    # VALIDATION VE SAYISAL KARARLILIK TESTLERİ
    # =========================================================================
    
    def test_input_validation_edge_cases(self):
        """Input validation edge case testleri"""
        
        T_test = np.array([1.0])
        
        # SDS=0 durumu (uyarı verir ama çalışır)
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sae_T, _, _ = self.calculator.calculate_horizontal_spectrum(T_test, 0.0, self.SD1, self.TL)
            self.assertTrue(len(w) > 0)  # Uyarı verilmeli
            self.assertIn("SDS=0", str(w[0].message))
            
        # SD1=0 durumu (uyarı verir ama çalışır)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            sae_T, _, _ = self.calculator.calculate_horizontal_spectrum(T_test, self.SDS, 0.0, self.TL)
            self.assertTrue(len(w) > 0)  # Uyarı verilmeli
            self.assertIn("SD1=0", str(w[0].message))
    
    def test_numerical_stability_zero_period(self):
        """Sayısal kararlılık: sıfıra yakın periyot değerleri"""
        
        # Çok küçük periyot değerleri
        T_small = np.array([1e-16, 1e-15, 1e-10, 0.0])
        
        sae_T, _, _ = self.calculator.calculate_horizontal_spectrum(T_small, self.SDS, self.SD1, self.TL)
        
        # Sonuçlar sonlu olmalı
        self.assertTrue(np.all(np.isfinite(sae_T)))
        
        # T≈0 değerleri için 0.4*SDS beklenir
        expected_zero = 0.4 * self.SDS
        self.assertAlmostEqual(sae_T[-1], expected_zero, places=10)  # T=0.0
        
    def test_nan_inf_handling(self):
        """NaN/Inf değerleri yönetimi"""
        
        # Çok büyük periyot değerleri (1/T² → 0'a gitmeli)
        T_large = np.array([1e10, 1e15])
        
        sae_T, _, _ = self.calculator.calculate_horizontal_spectrum(T_large, self.SDS, self.SD1, self.TL)
        
        # Sonuçlar sonlu ve pozitif olmalı
        self.assertTrue(np.all(np.isfinite(sae_T)))
        self.assertTrue(np.all(sae_T >= 0))
        
        # Çok büyük T için değerler çok küçük olmalı
        self.assertLess(sae_T[0], 1e-10)  # SD1*TL/T² formülü
        
    def test_vertical_spectrum_nan_preservation(self):
        """Düşey spektrumda NaN korunması (T > T_LD)"""
        
        # T_LD'den büyük değerler
        T_large = np.array([self.TL/2.0 + 1.0, self.TL + 1.0])
        
        saeD_T, _, _ = self.calculator.calculate_vertical_spectrum(T_large, self.SDS, self.SD1, self.TL)
        
        # T > T_LD için NaN olmalı
        self.assertTrue(np.all(np.isnan(saeD_T)))

    # =========================================================================
    # GENEL ENTEGRASYON TESTLERİ
    # =========================================================================
    
    def test_calculate_all_spectra_integration(self):
        """Tüm spektrumları hesaplama entegrasyon testi"""
        
        result = self.calculator.calculate_all_spectra(
            self.SDS, self.SD1, self.TL,
            include_horizontal=True,
            include_vertical=True,
            include_displacement=True
        )
        
        # DataFrame yapısı kontrolü
        df = result['dataframe']
        expected_columns = [
            'Yatay Spektral İvme (g)', 
            'Düşey Spektral İvme (g)',
            'Yatay Spektral Yerdeğiştirme (cm)'
        ]
        
        for col in expected_columns:
            self.assertIn(col, df.columns)
            
        # İndeks kontrolü - Periyot (s) artık indeks
        self.assertEqual(df.index.name, 'Periyot (s)')
        
        # Spectrum info yapısı kontrolü
        spectrum_info = result['spectrum_info']
        self.assertIn('horizontal', spectrum_info)
        self.assertIn('vertical', spectrum_info)
        self.assertIn('displacement', spectrum_info)
        
        # Her spektrum için gerekli bilgiler
        for spec_type in ['horizontal', 'vertical', 'displacement']:
            info = spectrum_info[spec_type]
            self.assertIn('data', info)
            self.assertIsInstance(info['data'], np.ndarray)
        
        # Period array kontrolü
        period_array = result['period_array']
        self.assertIsInstance(period_array, np.ndarray)
        self.assertEqual(len(period_array), len(df))


if __name__ == '__main__':
    # Test çalıştırma
    unittest.main(verbosity=2)
