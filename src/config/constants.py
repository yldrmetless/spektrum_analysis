"""
TBDY-2018 Spektrum Hesaplama Sabitleri ve Konfigürasyonlar
"""

# TBDY-2018 Parametreleri
TBDY_VERSION = "2018"

# ────────────────────────────────────────────────────────────────
# Basit Ölçeklendirme Sınır Sabitleri
# ────────────────────────────────────────────────────────────────
# TBDY-2018 3B basit ölçeklendirme için tavsiye edilen asgari kayıt takımı sayısı
MIN_RECORD_COUNT: int = 11
# Aynı depremden seçilebilecek azami kayıt takımı sayısı
MAX_SAME_EVENT_PER_SET: int = 3

# Deprem Düzeyleri
EARTHQUAKE_LEVELS = [
    'DD-1 (50 yılda aşılma olasılığı 2%)', 
    'DD-2 (50 yılda aşılma olasılığı 10%)', 
    'DD-3 (50 yılda aşılma olasılığı 25%)', 
    'DD-4 (50 yılda aşılma olasılığı 50%)'
]

# Zemin Sınıfları
SOIL_CLASSES = [
    'ZA Sınıfı Zemin', 
    'ZB Sınıfı Zemin', 
    'ZC Sınıfı Zemin', 
    'ZD Sınıfı Zemin', 
    'ZE Sınıfı Zemin', 
    'ZF Sınıfı Zemin'
]

# TBDY-2018 Tablo 2.1 - Kısa periyot bölgesi için Yerel Zemin Etki Katsayıları (Fs)
# Ss değer aralıkları: ≤0.25, 0.50, 0.75, 1.00, 1.25, ≥1.50
FS_VALUES = {
    'ZA': [0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
    'ZB': [0.9, 0.9, 0.9, 0.9, 0.9, 0.9],
    'ZC': [1.3, 1.3, 1.2, 1.2, 1.2, 1.2],
    'ZD': [1.6, 1.4, 1.2, 1.1, 1.0, 1.0],
    'ZE': [2.4, 1.7, 1.3, 1.1, 0.9, 0.8]
}

# TBDY-2018 Tablo 2.2 - 1.0 saniye periyot için Yerel Zemin Etki Katsayıları (F1)
# S1 değer aralıkları: ≤0.10, 0.20, 0.30, 0.40, 0.50, ≥0.60
F1_VALUES = {
    'ZA': [0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
    'ZB': [0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
    'ZC': [1.5, 1.5, 1.5, 1.5, 1.5, 1.4],
    'ZD': [2.4, 2.2, 2.0, 1.9, 1.8, 1.7],
    'ZE': [4.2, 3.3, 2.8, 2.4, 2.2, 2.0]
}

# Spektrum Hesaplama Sabitleri
DEFAULT_TL = 6.0  # Uzun periyot geçiş periyodu (saniye)
# Mühendislikte yaygın kabul gören standart yerçekimi ivmesi
GRAVITY = 9.80665     # m/s²
GRAVITY_CM = 981.0  # cm/s² (test beklentisiyle hizalı)

# Birim dönüşüm tabloları (merkezi kaynak)
# - "*_TO_BASE": birimi SI tabanına (m/s², m/s, m) dönüştürür
# - "BASE_TO_*": SI tabanından hedef birime dönüştürür

# İvme → m/s²
ACCEL_TO_BASE = {
    'g': GRAVITY,
    'm/s²': 1.0,
    'cm/s²': 0.01,
    'mm/s²': 0.001,
}

# m/s² → İvme birimleri
BASE_TO_ACCEL = {
    'm/s²': 1.0,
    'cm/s²': 100.0,
    'mm/s²': 1000.0,
    'g': 1.0 / GRAVITY,
}

# Hız → m/s
VEL_TO_BASE = {
    'm/s': 1.0,
    'cm/s': 0.01,
    'mm/s': 0.001,
    'km/h': 1.0 / 3.6,
}

# m/s → Hız birimleri
BASE_TO_VEL = {
    'm/s': 1.0,
    'cm/s': 100.0,
    'mm/s': 1000.0,
    'km/h': 3.6,
}

# Yerdeğiştirme → m
DISP_TO_BASE = {
    'm': 1.0,
    'cm': 0.01,
    'mm': 0.001,
    'μm': 1e-6,
    'km': 1000.0,
}

# m → Yerdeğiştirme birimleri
BASE_TO_DISP = {
    'm': 1.0,
    'cm': 100.0,
    'mm': 1000.0,
    'μm': 1_000_000.0,
    'km': 0.001,
}

# Zaman serisi örnekleme kontrolleri
# İki ardışık örnek aralığının medyana göre izin verilen bağıl sapması (örn. %2)
TIME_UNIFORMITY_TOLERANCE = 0.02

# Tablo performans ayarları
# Çok büyük veri setlerinde tabloya yazılacak maksimum satır sayıları
TABLE_MAX_POINTS_PEER = 1500
TABLE_MAX_POINTS_DEFAULT = 1000
TABLE_MAX_POINTS_LARGE = 750
TABLE_MAX_POINTS_VERY_LARGE = 500
TABLE_FAST_MODE_THRESHOLD = 2000  # Bu değerin üzerindeki listelerde hızlı formatlama kullan

# Düşey Spektrum Sabitleri - TBDY-2018 Uygun Değerler
VERTICAL_TA = 0.05  # Düşey spektrum köşe periyodu TA (saniye) - TBDY-2018
VERTICAL_TB = 0.15  # Düşey spektrum köşe periyodu TB (saniye) - TBDY-2018

# Grafik Ayarları
DEFAULT_FIGURE_SIZE = (10, 6)
DPI_SETTING = 300
POINT_COUNT = 1000  # Spektrum çizimi için nokta sayısı

# Dosya Formatları
SUPPORTED_EXCEL_FORMATS = [("Excel Dosyaları", "*.xlsx *.xls")]
SUPPORTED_CSV_FORMATS = [("CSV Dosyaları", "*.csv")]
SUPPORTED_IMAGE_FORMATS = [("PNG", "*.png"), ("JPEG", "*.jpg"), ("PDF", "*.pdf")]

# Deprem Kaydı Dosya Formatları
SUPPORTED_EARTHQUAKE_FORMATS = [
    ("Tüm Desteklenen Formatlar", "*.txt *.dat *.csv *.at2 *.asc *.vt2 *.dt2"),
    ("Metin Dosyaları", "*.txt"),
    ("Veri Dosyaları", "*.dat"),
    ("CSV Dosyaları", "*.csv"),
    ("AT2 Dosyaları (İvme)", "*.at2"),
    ("VT2 Dosyaları (Hız)", "*.vt2"),
    ("DT2 Dosyaları (Yerdeğiştirme)", "*.dt2"),
    ("ASC Dosyaları", "*.asc"),
    ("Tüm Dosyalar", "*.*")
]

# AFAD Veri Seti Sütun İndisleri (skiprows=3 sonrası)
AFAD_COLUMN_NAMES = [
    'Boylam', 'Enlem', 'PGA_DD1', 'PGA_DD2', 'PGA_DD3', 'PGA_DD4',
    'Ss_DD1', 'Ss_DD2', 'Ss_DD3', 'Ss_DD4', 'S1_DD1', 'S1_DD2',
    'S1_DD3', 'S1_DD4', 'PGV_DD4', 'PGV_DD3', 'PGV_DD2', 'PGV_DD1'
]

REQUIRED_AFAD_COLUMNS = [
    'Boylam', 'Enlem', 'PGA_DD1', 'PGA_DD2', 'PGA_DD3', 'PGA_DD4',
    'Ss_DD1', 'Ss_DD2', 'Ss_DD3', 'Ss_DD4',
    'S1_DD1', 'S1_DD2', 'S1_DD3', 'S1_DD4',
    'PGV_DD4', 'PGV_DD3', 'PGV_DD2', 'PGV_DD1'
]

# Uygulama Ayarları
DEFAULT_LOCATION = {"lat": 41.008073, "lon": 29.040003}  # Örnek koordinat
DEFAULT_EARTHQUAKE_LEVEL = "DD-2 (50 yılda aşılma olasılığı 10%)"
DEFAULT_SOIL_CLASS = "ZC Sınıfı Zemin" 

# Uygulama genelinde sol panel (sidebar) hedef genişliği (piksel)
# Tkinter piksel tabanlı olduğu için doğrudan int değer kullanılır
APP_SIDEBAR_WIDTH: int = 580

# Tab bazlı sol panel genişlikleri (piksel)
# Spektrum Oluşturma sekmesi için önerilen genişlik
SIDEBAR_WIDTH_SPECTRUM: int = 580  # tab-bazli-sol-panel-genislik.md: ~260px önerisi GUI'de piksel sabitine çevrilir
# Deprem Kayıtları sekmesi için önerilen genişlik
SIDEBAR_WIDTH_RECORDS: int = 450
