"""
SpectrumCalculator Test Sınıfı
Spektrum hesaplama işlevselliklerini test eder
"""

import unittest
import numpy as np
import pandas as pd
import sys
import os
from pathlib import Path

# Projenin src klasörünü Python path'ine ekle
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from calculations.spectrum import SpectrumCalculator

class TestSpectrumCalculator(unittest.TestCase):
    """SpectrumCalculator test sınıfı"""
    
    def setUp(self):
        """Test öncesi hazırlık"""
        self.calculator = SpectrumCalculator()
        
        # Test değerleri
        self.SDS = 1.2
        self.SD1 = 0.8
        self.TL = 6.0
        
        # Test periyot dizisi
        self.T_test = np.array([0.0, 0.1, 0.2, 0.5, 1.0, 2.0, 4.0, 8.0])
    
    def test_calculator_initialization(self):
        """Calculator başlatma testi"""
        calc = SpectrumCalculator()
        self.assertIsInstance(calc, SpectrumCalculator)
    
    def test_horizontal_spectrum_calculation(self):
        """Yatay spektrum hesaplama testi"""
        sae_T, TA, TB = self.calculator.calculate_horizontal_spectrum(
            self.T_test, self.SDS, self.SD1, self.TL
        )
        
        # Sonuç boyutu kontrolü
        self.assertEqual(len(sae_T), len(self.T_test))
        
        # Köşe periyotları kontrolü
        expected_TA = 0.2 * self.SD1 / self.SDS
        expected_TB = self.SD1 / self.SDS
        
        self.assertAlmostEqual(TA, expected_TA, places=6)
        self.assertAlmostEqual(TB, expected_TB, places=6)
        
        # T=0 için değer kontrolü
        self.assertAlmostEqual(sae_T[0], 0.4 * self.SDS, places=6)
        
        # Plato değeri kontrolü (TA < T < TB aralığında)
        plato_indices = np.where((self.T_test > TA) & (self.T_test <= TB))
        if len(plato_indices[0]) > 0:
            plato_values = sae_T[plato_indices]
            for val in plato_values:
                self.assertAlmostEqual(val, self.SDS, places=6)
    
    def test_vertical_spectrum_calculation(self):
        """Düşey spektrum hesaplama testi"""
        saeD_T, T_AD, T_BD = self.calculator.calculate_vertical_spectrum(
            self.T_test, self.SDS, self.SD1
        )
        
        # Sonuç boyutu kontrolü
        self.assertEqual(len(saeD_T), len(self.T_test))
        
        # Köşe periyotları kontrolü - TBDY-2018 güncel formülü
        expected_TA_h = 0.2 * self.SD1 / self.SDS
        expected_TB_h = self.SD1 / self.SDS
        expected_T_AD = expected_TA_h / 3.0
        expected_T_BD = expected_TB_h / 3.0
        
        self.assertAlmostEqual(T_AD, expected_T_AD, places=6)
        self.assertAlmostEqual(T_BD, expected_T_BD, places=6)
        
        # T=0 için değer kontrolü
        self.assertAlmostEqual(saeD_T[0], 0.32 * self.SDS, places=6)
        
        # Plato değeri kontrolü (T_AD < T <= T_BD aralığında)
        plato_indices = np.where((self.T_test > T_AD) & (self.T_test <= T_BD))
        if len(plato_indices[0]) > 0:
            plato_values = saeD_T[plato_indices]
            for val in plato_values:
                self.assertAlmostEqual(val, 0.8 * self.SDS, places=6)
    
    def test_displacement_spectrum_calculation(self):
        """Yerdeğiştirme spektrumu hesaplama testi"""
        sde_T, TA, TB = self.calculator.calculate_displacement_spectrum(
            self.T_test, self.SDS, self.SD1, self.TL
        )
        
        # Sonuç boyutu kontrolü
        self.assertEqual(len(sde_T), len(self.T_test))
        
        # T=0 için değer kontrolü (sıfır olmalı)
        self.assertEqual(sde_T[0], 0.0)
        
        # Pozitif değerler kontrolü (T>0 için)
        positive_T_indices = np.where(self.T_test > 0)
        if len(positive_T_indices[0]) > 0:
            positive_sde = sde_T[positive_T_indices]
            self.assertTrue(np.all(positive_sde >= 0))
    
    def test_period_array_generation(self):
        """Periyot dizisi oluşturma testi"""
        T_basic = self.calculator.generate_period_array_optimized(
            self.SDS, self.SD1, self.TL
        )
        T_optimized = self.calculator.generate_period_array_optimized(
            self.SDS, self.SD1, self.TL
        )
        
        # Dizilerin boş olmaması
        self.assertGreater(len(T_basic), 0)
        self.assertGreater(len(T_optimized), 0)
        
        # Sıralı olma kontrolü
        self.assertTrue(np.all(T_basic[1:] >= T_basic[:-1]))
        self.assertTrue(np.all(T_optimized[1:] >= T_optimized[:-1]))
        
        # Pozitif değerler
        self.assertTrue(np.all(T_basic >= 0))
        self.assertTrue(np.all(T_optimized > 0))
    
    def test_all_spectra_calculation(self):
        """Tüm spektrum türleri hesaplama testi"""
        result = self.calculator.calculate_all_spectra(
            self.SDS, self.SD1, self.TL,
            include_horizontal=True,
            include_vertical=True,
            include_displacement=True
        )
        
        # Sonuç yapısı kontrolü
        self.assertIn('dataframe', result)
        self.assertIn('period_array', result)
        self.assertIn('spectrum_info', result)
        
        # DataFrame kontrolü
        df = result['dataframe']
        self.assertIsInstance(df, pd.DataFrame)
        self.assertIn('Periyot (s)', df.columns)
        self.assertIn('Yatay Spektral İvme (g)', df.columns)
        self.assertIn('Düşey Spektral İvme (g)', df.columns)
        self.assertIn('Yatay Spektral Yerdeğiştirme (cm)', df.columns)
        
        # Spectrum info kontrolü
        info = result['spectrum_info']
        self.assertIn('horizontal', info)
        self.assertIn('vertical', info)
        self.assertIn('displacement', info)
        
        # Her spektrum türü için gerekli bilgiler
        # Horizontal ve displacement için
        for spectrum_type in ['horizontal', 'displacement']:
            spectrum_info = info[spectrum_type]
            self.assertIn('data', spectrum_info)
            self.assertIn('TA', spectrum_info)
            self.assertIn('TB', spectrum_info)
        
        # Vertical için farklı anahtar isimleri
        if 'vertical' in info:
            v_info = info['vertical']
            self.assertIn('data', v_info)
            self.assertIn('T_AD', v_info)
            self.assertIn('T_BD', v_info)
    
    def test_selective_spectrum_calculation(self):
        """Seçici spektrum hesaplama testi"""
        # Sadece yatay spektrum
        result_horizontal = self.calculator.calculate_all_spectra(
            self.SDS, self.SD1, self.TL,
            include_horizontal=True,
            include_vertical=False,
            include_displacement=False
        )
        
        info = result_horizontal['spectrum_info']
        self.assertIn('horizontal', info)
        self.assertNotIn('vertical', info)
        self.assertNotIn('displacement', info)
        
        # Sadece düşey spektrum
        result_vertical = self.calculator.calculate_all_spectra(
            self.SDS, self.SD1, self.TL,
            include_horizontal=False,
            include_vertical=True,
            include_displacement=False
        )
        
        info = result_vertical['spectrum_info']
        self.assertNotIn('horizontal', info)
        self.assertIn('vertical', info)
        self.assertNotIn('displacement', info)
    
    def test_edge_cases(self):
        """Uç durumlar testi"""
        # SDS = 0 durumu
        sae_T_zero, TA_zero, TB_zero = self.calculator.calculate_horizontal_spectrum(
            self.T_test, 0.0, self.SD1, self.TL
        )
        
        self.assertEqual(TA_zero, 0.0)
        self.assertEqual(TB_zero, 0.0)
        
        # SD1 = 0 durumu
        sae_T_zero_sd1, TA_zero_sd1, TB_zero_sd1 = self.calculator.calculate_horizontal_spectrum(
            self.T_test, self.SDS, 0.0, self.TL
        )
        
        self.assertEqual(TA_zero_sd1, 0.0)
        self.assertEqual(TB_zero_sd1, 0.0)
    
    def test_consistency_check(self):
        """Tutarlılık kontrolü testi"""
        # Aynı parametrelerle iki kez hesapla
        result1 = self.calculator.calculate_all_spectra(
            self.SDS, self.SD1, self.TL,
            include_horizontal=True,
            include_vertical=True
        )
        
        result2 = self.calculator.calculate_all_spectra(
            self.SDS, self.SD1, self.TL,
            include_horizontal=True,
            include_vertical=True
        )
        
        # Sonuçların aynı olması
        df1 = result1['dataframe']
        df2 = result2['dataframe']
        
        pd.testing.assert_frame_equal(df1, df2)
    
    def test_physical_constraints(self):
        """Fiziksel kısıtlar testi"""
        sae_T, TA, TB = self.calculator.calculate_horizontal_spectrum(
            self.T_test, self.SDS, self.SD1, self.TL
        )
        
        # Negatif değer olmaması
        self.assertTrue(np.all(sae_T >= 0))
        
        # Köşe periyotlarının pozitif olması
        self.assertGreaterEqual(TA, 0)
        self.assertGreaterEqual(TB, 0)
        
        # TA <= TB koşulu
        self.assertLessEqual(TA, TB)
    
    def test_tbdy_2018_compliance(self):
        """TBDY-2018 uyumluluk testi"""
        # Test parametreleri ile spektrum hesapla
        result = self.calculator.calculate_all_spectra(
            self.SDS, self.SD1, self.TL,
            include_horizontal=True,
            include_vertical=True
        )
        
        # Yatay spektrum için TBDY-2018 köşe periyotları
        h_info = result['spectrum_info']['horizontal']
        expected_TA = 0.2 * self.SD1 / self.SDS
        expected_TB = self.SD1 / self.SDS
        
        self.assertAlmostEqual(h_info['TA'], expected_TA, places=6)
        self.assertAlmostEqual(h_info['TB'], expected_TB, places=6)
        
        # Düşey spektrum için TBDY-2018 köşe periyotları
        v_info = result['spectrum_info']['vertical']
        expected_T_AD = expected_TA / 3.0
        expected_T_BD = expected_TB / 3.0
        
        self.assertAlmostEqual(v_info['T_AD'], expected_T_AD, places=6)
        self.assertAlmostEqual(v_info['T_BD'], expected_T_BD, places=6)

if __name__ == '__main__':
    unittest.main() 