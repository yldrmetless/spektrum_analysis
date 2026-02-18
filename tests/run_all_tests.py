"""
Tüm Testleri Çalıştırma Script'i
TBDY-2018 Spektrum Analizi için kapsamlı test suite
"""

import unittest
import sys
import os
from pathlib import Path
import time
from io import StringIO

# Projenin src klasörünü Python path'ine ekle
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Test modüllerini import et
from test_unit_converter import TestUnitConverter
from test_spectrum_calculator import TestSpectrumCalculator
from test_file_utils import TestFileUtils

# Response Spectrum testlerini import et (opsiyonel)
try:
    from test_response_spectrum import TestResponseSpectrum, TestResponseSpectrumIntegration
    RESPONSE_SPECTRUM_TESTS_AVAILABLE = True
except ImportError:
    RESPONSE_SPECTRUM_TESTS_AVAILABLE = False

class TestRunner:
    """Test çalıştırıcı sınıfı"""
    
    def __init__(self):
        """Test runner başlatıcısı"""
        self.test_results = {}
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.error_tests = 0
        self.skipped_tests = 0
    
    def run_test_suite(self, test_class, suite_name):
        """
        Bir test suite'ini çalıştırır
        
        Args:
            test_class: Test sınıfı
            suite_name (str): Test suite adı
        """
        print(f"\n🧪 {suite_name} Testleri Çalıştırılıyor...")
        print("-" * 50)
        
        # Test suite oluştur
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(test_class)
        
        # Test sonuçlarını yakala
        stream = StringIO()
        runner = unittest.TextTestRunner(
            stream=stream, 
            verbosity=2,
            failfast=False
        )
        
        # Zaman ölçümü
        start_time = time.time()
        result = runner.run(suite)
        end_time = time.time()
        
        # Sonuçları sakla
        self.test_results[suite_name] = {
            'result': result,
            'duration': end_time - start_time,
            'output': stream.getvalue()
        }
        
        # İstatistikleri güncelle
        self.total_tests += result.testsRun
        self.passed_tests += result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
        self.failed_tests += len(result.failures)
        self.error_tests += len(result.errors)
        self.skipped_tests += len(result.skipped)
        
        # Sonuç özeti yazdır
        self._print_suite_summary(suite_name, result, end_time - start_time)
        
        return result
    
    def _print_suite_summary(self, suite_name, result, duration):
        """Test suite özeti yazdırır"""
        status = "✅ BAŞARILI" if result.wasSuccessful() else "❌ BAŞARISIZ"
        
        print(f"\n{suite_name} Sonuçları: {status}")
        print(f"📊 Test Sayısı: {result.testsRun}")
        print(f"✅ Başarılı: {result.testsRun - len(result.failures) - len(result.errors)}")
        print(f"❌ Başarısız: {len(result.failures)}")
        print(f"💥 Hata: {len(result.errors)}")
        print(f"⏭️ Atlandı: {len(result.skipped)}")
        print(f"⏱️ Süre: {duration:.2f} saniye")
        
        # Başarısızlık detayları
        if result.failures:
            print(f"\n❌ Başarısız Testler:")
            for test, error in result.failures:
                print(f"  • {test}: {error.split('AssertionError: ')[-1].split(chr(10))[0]}")
        
        # Hata detayları
        if result.errors:
            print(f"\n💥 Hatalı Testler:")
            for test, error in result.errors:
                error_line = error.split('\n')[-2] if '\n' in error else error
                print(f"  • {test}: {error_line}")
    
    def run_all_tests(self):
        """Tüm test suite'lerini çalıştırır"""
        print("🚀 TBDY-2018 Spektrum Analizi Test Suite'i Başlatılıyor...")
        print("=" * 70)
        
        start_time = time.time()
        
        # Test suite'lerini tanımla
        test_suites = [
            (TestUnitConverter, "Birim Dönüştürücü"),
            (TestSpectrumCalculator, "Spektrum Hesaplayıcı"),
            (TestFileUtils, "Dosya İşlemleri")
        ]
        
        # Response Spectrum testlerini ekle (varsa)
        if RESPONSE_SPECTRUM_TESTS_AVAILABLE:
            test_suites.extend([
                (TestResponseSpectrum, "Response Spectrum"),
                (TestResponseSpectrumIntegration, "Response Spectrum Entegrasyon")
            ])
        
        # Her test suite'ini çalıştır
        all_successful = True
        for test_class, suite_name in test_suites:
            try:
                result = self.run_test_suite(test_class, suite_name)
                if not result.wasSuccessful():
                    all_successful = False
            except Exception as e:
                print(f"❌ {suite_name} test suite'i çalıştırılırken hata: {e}")
                all_successful = False
        
        end_time = time.time()
        
        # Genel özet
        self._print_final_summary(end_time - start_time, all_successful)
        
        return all_successful
    
    def _print_final_summary(self, total_duration, all_successful):
        """Final özet yazdırır"""
        print("\n" + "=" * 70)
        print("🏁 GENEL TEST ÖZETİ")
        print("=" * 70)
        
        status = "✅ TÜM TESTLER BAŞARILI" if all_successful else "❌ BAZI TESTLER BAŞARISIZ"
        print(f"Durum: {status}")
        print(f"📊 Toplam Test: {self.total_tests}")
        print(f"✅ Başarılı: {self.passed_tests}")
        print(f"❌ Başarısız: {self.failed_tests}")
        print(f"💥 Hata: {self.error_tests}")
        print(f"⏭️ Atlandı: {self.skipped_tests}")
        print(f"⏱️ Toplam Süre: {total_duration:.2f} saniye")
        
        if self.total_tests > 0:
            success_rate = (self.passed_tests / self.total_tests) * 100
            print(f"📈 Başarı Oranı: {success_rate:.1f}%")
        
        # Detaylı suite sonuçları
        print(f"\n📋 Suite Detayları:")
        for suite_name, suite_data in self.test_results.items():
            result = suite_data['result']
            duration = suite_data['duration']
            status_icon = "✅" if result.wasSuccessful() else "❌"
            print(f"  {status_icon} {suite_name}: {result.testsRun} test, {duration:.2f}s")
    
    def run_specific_test(self, test_class, test_method=None):
        """Belirli bir testi çalıştırır"""
        if test_method:
            suite = unittest.TestSuite()
            suite.addTest(test_class(test_method))
        else:
            loader = unittest.TestLoader()
            suite = loader.loadTestsFromTestCase(test_class)
        
        runner = unittest.TextTestRunner(verbosity=2)
        return runner.run(suite)

def main():
    """Ana test fonksiyonu"""
    # Command line argümanlarını kontrol et
    if len(sys.argv) > 1:
        test_arg = sys.argv[1].lower()
        
        if test_arg == 'unit':
            print("🧪 Sadece Birim Dönüştürücü testleri çalıştırılıyor...")
            runner = TestRunner()
            result = runner.run_test_suite(TestUnitConverter, "Birim Dönüştürücü")
            return result.wasSuccessful()
        
        elif test_arg == 'spectrum':
            print("🧪 Sadece Spektrum Hesaplayıcı testleri çalıştırılıyor...")
            runner = TestRunner()
            result = runner.run_test_suite(TestSpectrumCalculator, "Spektrum Hesaplayıcı")
            return result.wasSuccessful()
        
        elif test_arg == 'file':
            print("🧪 Sadece Dosya İşlemleri testleri çalıştırılıyor...")
            runner = TestRunner()
            result = runner.run_test_suite(TestFileUtils, "Dosya İşlemleri")
            return result.wasSuccessful()
        
        elif test_arg == 'response' and RESPONSE_SPECTRUM_TESTS_AVAILABLE:
            print("🧪 Sadece Response Spectrum testleri çalıştırılıyor...")
            runner = TestRunner()
            result1 = runner.run_test_suite(TestResponseSpectrum, "Response Spectrum")
            result2 = runner.run_test_suite(TestResponseSpectrumIntegration, "Response Spectrum Entegrasyon")
            return result1.wasSuccessful() and result2.wasSuccessful()
        
        elif test_arg == 'help':
            print("Kullanım:")
            print("  python run_all_tests.py        - Tüm testleri çalıştır")
            print("  python run_all_tests.py unit   - Sadece birim testlerini çalıştır")
            print("  python run_all_tests.py spectrum - Sadece spektrum testlerini çalıştır")
            print("  python run_all_tests.py file   - Sadece dosya testlerini çalıştır")
            if RESPONSE_SPECTRUM_TESTS_AVAILABLE:
                print("  python run_all_tests.py response - Sadece response spectrum testlerini çalıştır")
            print("  python run_all_tests.py help   - Bu yardım mesajını göster")
            return True
        
        else:
            print(f"❌ Bilinmeyen parametre: {test_arg}")
            print("Yardım için: python run_all_tests.py help")
            return False
    
    # Tüm testleri çalıştır
    runner = TestRunner()
    return runner.run_all_tests()

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Testler kullanıcı tarafından iptal edildi.")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test runner'da beklenmeyen hata: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 