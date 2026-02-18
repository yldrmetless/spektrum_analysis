# 3B Ölçekleme Modülleri

PGMD uyumlu 3B ölçekleme işlemleri için kapsamlı modül paketi.

## Özellikler

- **PGMD Uyumlu**: PEER Ground Motion Database standartlarına uygun
- **301 Nokta Grid**: 0.01-10 s aralığında log-uzay periyot ızgarası
- **3B Ölçekleme**: FN/FP/V bileşenleri için geometrik ortalama tabanlı ölçekleme
- **Çoklu Ölçekleme Modu**: No Scaling, Minimize MSE ve Single Period seçenekleri
- **MSE Tabanlı Sıralama**: Log-uzayda minimum kare hata optimizasyonu
- **Yönetmelik Kontrolleri**: ASCE 7-16 ve TBDY uyumluluk kontrolleri
- **Kapsamlı Raporlama**: JSON, CSV, TXT formatlarında dışa aktarma

## Modül Yapısı

```
src/scaling/
├── __init__.py                 # Ana modül girişi
├── scaling_3d_main.py         # Ana koordinatör sınıf
├── period_grid.py             # Periyot ızgarası
├── weight_function.py         # Ağırlık fonksiyonları
├── scale_factor.py           # Ölçek katsayısı hesaplama
├── scale_3d.py               # 3B ölçekleme
├── ranking_selection.py      # Kayıt sıralama ve seçim
├── regulatory_checks.py      # Yönetmelik kontrolleri
├── reporting.py             # Raporlama ve dışa aktarma
├── example_usage.py          # Kullanım örnekleri
└── README.md                 # Bu dosya
```

## Hızlı Başlangıç

### Temel Kullanım

```python
from src.scaling import Scaling3DProcessor, create_default_config

# Konfigürasyon
config = create_default_config()
processor = Scaling3DProcessor(config)

# Hedef spektrumu ayarla
processor.set_target_spectrum(target_spectrum)

# Kayıtları işle
processor.process_records(records_data, metadata)

# Yönetmelik kontrollerini yap
processor.perform_regulatory_checks(T_design=1.0)

# Sonuçları dışa aktar
files_created = processor.export_results(T_design=1.0)
```

### Özel Konfigürasyon

```python
from src.scaling import Scaling3DConfig

config = Scaling3DConfig(
    mode="range",                    # "single" veya "range"
    weight_type="custom",            # Ağırlık fonksiyonu tipi
    weight_params={                  # Özel ağırlık parametreleri
        "period_knots": np.array([0.1, 0.5, 1.0, 2.0, 5.0]),
        "weight_knots": np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    },
    scale_limits=(0.1, 10.0),       # Ölçek katsayısı sınırları
    filter_criteria={               # Filtreleme kriterleri
        "max_mse": 1.0,
        "min_scale_factor": 0.1,
        "max_scale_factor": 10.0
    },
    n_top_records=10,               # En iyi N kayıt
    output_dir="output"             # Çıktı dizini
)
```

## Modül Detayları

### 1. Periyot Izgarası (`period_grid.py`)

- **301 nokta**: 0.01-10 s aralığında log-uzay
- **Dekad başına 100 nokta**: PGMD standardı
- **Interpolasyon**: Mevcut verileri ızgaraya uyarlama

```python
from src.scaling import build_period_grid, validate_period_grid

T = build_period_grid()  # 301 nokta
is_valid, message = validate_period_grid(T)
```

### 2. Ağırlık Fonksiyonu (`weight_function.py`)

- **Uniform**: Eşit ağırlık
- **Custom**: Kullanıcı tanımlı
- **Short Period**: Kısa periyotlara odaklanma
- **Long Period**: Uzun periyotlara odaklanma
- **Band**: Belirli periyot bandına odaklanma

```python
from src.scaling import create_weight_function, create_uniform_weights

# Özel ağırlık
weights = create_weight_function(period_knots, weight_knots, T_grid)

# Uniform ağırlık
weights = create_uniform_weights(T_grid)
```

### 3. Ölçek Katsayısı (`scale_factor.py`)

- **Tek periyot**: f = SA_target(T_s) / SA_record(T_s)
- **Aralık**: Kapalı form çözüm (MSE minimizasyonu)
- **3B ölçekleme**: Geometrik ortalama tabanlı

```python
from src.scaling import calculate_scale_factor, calculate_scale_factor_3d

# Tek periyot
f, mse = calculate_scale_factor(SA_target, SA_record, weights, mode="single", T_s=1.0)

# Aralık
f, mse = calculate_scale_factor(SA_target, SA_record, weights, mode="range")

# 3B
f, mse, SA_GM = calculate_scale_factor_3d(SA_target, SA_FN, SA_FP, weights)
```

### 4. 3B Ölçekleme (`scale_3d.py`)

- **FN/FP/V bileşenleri**: Aynı ölçek katsayısı ile
- **Geometrik ortalama**: SA_GM = √(SA_FN × SA_FP)
- **Suite istatistikleri**: Aritmetik ve geometrik ortalamalar

```python
from src.scaling import scale_record_3d, scale_multiple_records_3d

# Tek kayıt
result = scale_record_3d(SA_target, SA_FN, SA_FP, SA_V, weights)

# Çoklu kayıt
results = scale_multiple_records_3d(SA_target, records_data, weights)
```

### 5. Sıralama ve Seçim (`ranking_selection.py`)

- **MSE tabanlı sıralama**: Düşük MSE → yüksek sıra
- **Filtreleme**: LUF, mesafe, VS30, pulse kriterleri
- **En iyi N kayıt**: Otomatik seçim

```python
from src.scaling import rank_records_by_mse, select_top_records, filter_records_by_criteria

# Sıralama
ranking = rank_records_by_mse(results, metadata)

# Filtreleme
valid_indices, filtered_results, filtered_metadata = filter_records_by_criteria(
    results, metadata, criteria
)

# En iyi kayıtlar
top_results, top_metadata, top_indices = select_top_records(
    results, metadata, n_top=10
)
```

### 6. Yönetmelik Kontrolleri (`regulatory_checks.py`)

- **ASCE 7-16**: 0.2T-2.0T bandında %90 eşik
- **TBDY**: 0.2T-1.5T bandında %90 eşik
- **Spektral şekil**: Şekil uyumluluğu kontrolü

```python
from src.scaling import perform_comprehensive_regulatory_checks

checks = perform_comprehensive_regulatory_checks(
    results, target_spectrum, T_design, component="GM"
)
```

### 7. Raporlama (`reporting.py`)

- **JSON**: Yapılandırılmış veri
- **CSV**: Tablo formatı
- **TXT**: Özet rapor
- **Spektral diziler**: Ayrı CSV dosyaları

```python
from src.scaling import export_comprehensive_report

files_created = export_comprehensive_report(
    results, metadata, ranking, regulatory_checks,
    target_spectrum, T_grid, scaling_params, output_dir
)
```

## Veri Formatları

### Kayıt Verisi

```python
records_data = [
    {
        "SA_FN": np.array([...]),    # 301 nokta
        "SA_FP": np.array([...]),    # 301 nokta
        "SA_V": np.array([...])      # 301 nokta (opsiyonel)
    },
    # ... daha fazla kayıt
]
```

### Meta Veri

```python
metadata = [
    RecordMetadata(
        nga_number="NGA0001",
        pulse=True,
        pulse_period=0.5,
        duration_5_95=15.0,
        r_rup=25.0,
        r_jb=20.0,
        vs30=300.0,
        lowest_usable_freq=0.1,
        pga=0.2,
        pgv=0.1,
        pgd=0.01,
        file_names={"FN": "file_FN.txt", "FP": "file_FP.txt", "V": "file_V.txt"}
    ),
    # ... daha fazla meta veri
]
```

## Örnekler

Detaylı örnekler için `example_usage.py` dosyasına bakın:

- Temel 3B ölçekleme
- Özel ağırlık fonksiyonu
- Filtreleme
- Dışa aktarma
- Gelişmiş konfigürasyon

## Gereksinimler

- Python 3.8+
- NumPy
- Pandas
- SciPy (opsiyonel, optimizasyon için)

## Lisans

Bu modül doktora tez projesi kapsamında geliştirilmiştir.
