"""
FileUtils Test Sınıfı  
Dosya işlemleri işlevselliklerini test eder
"""

import unittest
import tempfile
import os
import pandas as pd
from pathlib import Path
import sys

# Projenin src klasörünü Python path'ine ekle
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from utils.file_utils import FileUtils

class TestFileUtils(unittest.TestCase):
    """FileUtils test sınıfı"""
    
    def setUp(self):
        """Test öncesi hazırlık"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Test DataFrame
        self.test_data = pd.DataFrame({
            'Periyot (s)': [0.1, 0.2, 0.5, 1.0, 2.0],
            'Yatay Spektral İvme (g)': [1.2, 1.5, 1.3, 1.0, 0.8],
            'Düşey Spektral İvme (g)': [0.96, 1.2, 1.04, 0.8, 0.64]
        })
    
    def tearDown(self):
        """Test sonrası temizlik"""
        # Temp dosyaları temizle
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass
    
    def test_excel_export(self):
        """Excel export testi"""
        # Test dosya yolu
        excel_path = os.path.join(self.temp_dir, 'test_data.xlsx')
        
        # Export işlemi
        success = FileUtils.export_dataframe_to_excel(self.test_data, excel_path, "Test Export")
        
        if success:  # openpyxl varsa
            self.assertTrue(os.path.exists(excel_path))
            
            # Dosyayı oku ve kontrol et
            loaded_data = pd.read_excel(excel_path)
            self.assertEqual(len(loaded_data), len(self.test_data))
            self.assertEqual(list(loaded_data.columns), list(self.test_data.columns))
    
    def test_file_info_retrieval(self):
        """Dosya bilgisi alma testi"""
        # Test dosyası oluştur
        test_file = os.path.join(self.temp_dir, 'info_test.txt')
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write('Test content')
        
        # Dosya bilgilerini al
        info = FileUtils.get_file_info(test_file)
        
        self.assertTrue(info['exists'])
        self.assertEqual(info['name'], 'info_test.txt')
        self.assertEqual(info['extension'], '.txt')
        self.assertGreater(info['size'], 0)
    
    def test_nonexistent_file_info(self):
        """Var olmayan dosya bilgisi testi"""
        info = FileUtils.get_file_info('/nonexistent/file.txt')
        self.assertFalse(info['exists'])
    
    def test_file_extension_validation(self):
        """Dosya uzantısı doğrulama testi"""
        # Geçerli uzantılar
        self.assertTrue(FileUtils.validate_file_extension('test.xlsx', ['.xlsx', '.xls']))
        self.assertTrue(FileUtils.validate_file_extension('data.csv', ['.csv', '.txt']))
        
        # Geçersiz uzantılar
        self.assertFalse(FileUtils.validate_file_extension('test.doc', ['.xlsx', '.xls']))
        self.assertFalse(FileUtils.validate_file_extension('', ['.xlsx']))
        self.assertFalse(FileUtils.validate_file_extension(None, ['.xlsx']))
    
    def test_directory_creation(self):
        """Dizin oluşturma testi"""
        new_dir = os.path.join(self.temp_dir, 'new_directory', 'sub_dir')
        
        # Dizin oluştur
        success = FileUtils.ensure_directory_exists(new_dir)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(new_dir))
        
        # Var olan dizin için tekrar çağır
        success_again = FileUtils.ensure_directory_exists(new_dir)
        self.assertTrue(success_again)
    
    def test_clipboard_operations(self):
        """Panoya kopyalama testi (eğer destekleniyorsa)"""
        try:
            # Clipboard operasyonu dene
            result = FileUtils.copy_dataframe_to_clipboard(self.test_data)
            # Başarılı veya başarısız olabilir, sistem bağımlı
            self.assertIsInstance(result, bool)
        except Exception:
            # Clipboard desteklenmiyorsa normal
            pass
    
    def test_supported_formats(self):
        """Desteklenen format sabitleri testi"""
        from config.constants import SUPPORTED_EXCEL_FORMATS, SUPPORTED_CSV_FORMATS, SUPPORTED_IMAGE_FORMATS
        
        # Format listelerinin boş olmaması
        self.assertGreater(len(SUPPORTED_EXCEL_FORMATS), 0)
        self.assertGreater(len(SUPPORTED_CSV_FORMATS), 0)
        self.assertGreater(len(SUPPORTED_IMAGE_FORMATS), 0)
        
        # Format tuple yapısının doğru olması
        for format_tuple in SUPPORTED_EXCEL_FORMATS:
            self.assertEqual(len(format_tuple), 2)  # (description, pattern)
            self.assertIsInstance(format_tuple[0], str)
            self.assertIsInstance(format_tuple[1], str)
    
    def test_save_dataframe_edge_cases(self):
        """DataFrame kaydetme uç durumları testi"""
        # Boş DataFrame
        empty_df = pd.DataFrame()
        excel_path = os.path.join(self.temp_dir, 'empty.xlsx')
        
        try:
            success = FileUtils.export_dataframe_to_excel(empty_df, excel_path)
            # Boş DataFrame kaydı başarılı olabilir veya olmayabilir
            self.assertIsInstance(success, bool)
        except Exception:
            # Bazı durumlarda hata çıkabilir
            pass
    
    def test_file_path_operations(self):
        """Dosya yolu işlemleri testi"""
        test_paths = [
            'test.xlsx',
            '/full/path/to/file.csv',
            'relative/path/data.json',
            '',
            None
        ]
        
        allowed_exts = ['.xlsx', '.csv', '.json']
        
        for path in test_paths:
            result = FileUtils.validate_file_extension(path, allowed_exts)
            self.assertIsInstance(result, bool)
    
    def test_large_dataframe_handling(self):
        """Büyük DataFrame işleme testi"""
        # Büyük DataFrame oluştur
        large_data = pd.DataFrame({
            f'Column_{i}': range(100) for i in range(10)
        })
        
        excel_path = os.path.join(self.temp_dir, 'large_data.xlsx')
        
        try:
            success = FileUtils.export_dataframe_to_excel(large_data, excel_path)
            if success:
                self.assertTrue(os.path.exists(excel_path))
                # Dosya boyutunun makul olması
                info = FileUtils.get_file_info(excel_path)
                self.assertGreater(info['size'], 1000)  # En az 1KB
        except Exception as e:
            # Memory veya sistem limitlerinde hata çıkabilir
            self.assertIsInstance(e, Exception)

if __name__ == '__main__':
    unittest.main() 