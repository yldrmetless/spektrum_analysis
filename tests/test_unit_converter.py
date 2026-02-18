"""
UnitConverter Test Sınıfı
Birim dönüştürme işlevselliklerini test eder
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

from utils.unit_converter import UnitConverter

class TestUnitConverter(unittest.TestCase):
    """UnitConverter test sınıfı"""
    
    def setUp(self):
        """Test öncesi hazırlık"""
        self.test_values = [1.0, 2.5, 0.1, 10.0]
        self.test_series = pd.Series([1.0, 2.0, 3.0])
    
    def test_get_supported_units(self):
        """Desteklenen birimler test edilir"""
        acc_units = UnitConverter.get_supported_acceleration_units()
        disp_units = UnitConverter.get_supported_displacement_units()
        
        self.assertIn('g', acc_units)
        self.assertIn('ms²', acc_units)
        self.assertIn('cms²', acc_units)
        
        self.assertIn('cm', disp_units)
        self.assertIn('m', disp_units)
        self.assertIn('mm', disp_units)
    
    def test_acceleration_conversion_g_to_ms2(self):
        """g'den m/s²'ye dönüşüm testi"""
        result = UnitConverter.convert_acceleration(1.0, 'g', 'ms²')
        expected = 9.81  # GRAVITY constant güncellenmiş
        self.assertAlmostEqual(result, expected, places=2)
    
    def test_acceleration_conversion_g_to_cms2(self):
        """g'den cm/s²'ye dönüşüm testi"""
        result = UnitConverter.convert_acceleration(1.0, 'g', 'cms²')
        expected = 981.0  # GRAVITY_CM constant güncellenmiş
        self.assertAlmostEqual(result, expected, places=1)
    
    def test_acceleration_conversion_ms2_to_g(self):
        """m/s²'den g'ye dönüşüm testi"""
        result = UnitConverter.convert_acceleration(9.81, 'ms²', 'g')
        expected = 1.0
        self.assertAlmostEqual(result, expected, places=2)
    
    def test_acceleration_conversion_same_unit(self):
        """Aynı birim dönüşüm testi"""
        result = UnitConverter.convert_acceleration(5.0, 'g', 'g')
        self.assertEqual(result, 5.0)
    
    def test_displacement_conversion_cm_to_m(self):
        """cm'den m'ye dönüşüm testi"""
        result = UnitConverter.convert_displacement(100.0, 'cm', 'm')
        expected = 1.0
        self.assertEqual(result, expected)
    
    def test_displacement_conversion_m_to_mm(self):
        """m'den mm'ye dönüşüm testi"""
        result = UnitConverter.convert_displacement(1.0, 'm', 'mm')
        expected = 1000.0
        self.assertEqual(result, expected)
    
    def test_conversion_with_array(self):
        """Array dönüşüm testi"""
        input_array = np.array([1.0, 2.0, 3.0])
        result = UnitConverter.convert_acceleration(input_array, 'g', 'ms²')
        expected = input_array * 9.81
        np.testing.assert_array_almost_equal(result, expected, decimal=2)
    
    def test_conversion_with_pandas_series(self):
        """Pandas Series dönüşüm testi"""
        result = UnitConverter.convert_acceleration(self.test_series, 'g', 'ms²')
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), len(self.test_series))
    
    def test_invalid_unit_conversion(self):
        """Geçersiz birim dönüşüm testi"""
        with self.assertRaises(ValueError):
            UnitConverter.convert_acceleration(1.0, 'invalid_unit', 'g')
        
        with self.assertRaises(ValueError):
            UnitConverter.convert_displacement(1.0, 'cm', 'invalid_unit')
    
    def test_unit_info_retrieval(self):
        """Birim bilgisi alma testi"""
        info = UnitConverter.get_unit_info('acceleration', 'g')
        self.assertEqual(info['symbol'], 'g')
        self.assertEqual(info['name'], 'Yerçekimi İvmesi')  # Güncel isim
    
    def test_unit_selection_options(self):
        """Birim seçim seçenekleri testi"""
        options = UnitConverter.create_unit_selection_options()
        self.assertIn('acceleration', options)
        self.assertIn('displacement', options)
        
        self.assertTrue(len(options['acceleration']) >= 3)
        self.assertTrue(len(options['displacement']) >= 3)
        
        # Display name format kontrolü
        acc_option = options['acceleration'][0]
        self.assertIn('display_name', acc_option)
        self.assertIn('code', acc_option)
        self.assertIn('symbol', acc_option)
    
    def test_auto_unit_detection(self):
        """Otomatik birim tespiti testi"""
        result1 = UnitConverter.auto_detect_unit_from_column_name("Yatay Spektral İvme (g)")
        self.assertEqual(result1['type'], 'acceleration')
        self.assertEqual(result1['unit'], 'g')
        
        result2 = UnitConverter.auto_detect_unit_from_column_name("Yatay Spektral Yerdeğiştirme (cm)")
        self.assertEqual(result2['type'], 'displacement')
        self.assertEqual(result2['unit'], 'cm')
    
    def test_format_value_with_unit(self):
        """Birim ile değer formatlama testi"""
        result = UnitConverter.format_value_with_unit(1.234, 'acceleration', 'g', precision=2)
        expected = "1.23 g"
        self.assertEqual(result, expected)
    
    def test_validate_conversion(self):
        """Birim dönüştürme doğrulama testi"""
        is_valid, message = UnitConverter.validate_conversion('g', 'ms²', 'acceleration')
        self.assertTrue(is_valid)
        
        is_valid, message = UnitConverter.validate_conversion('g', 'cm', 'acceleration')
        self.assertFalse(is_valid)

if __name__ == '__main__':
    unittest.main() 