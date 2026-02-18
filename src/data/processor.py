"""
AFAD verilerini işleme ve sorgu işlemleri – TAM GÜNCEL
"""

import re
import numpy as np
import pandas as pd
from typing import Dict, List
from config.constants import (
    ACCEL_TO_BASE, BASE_TO_VEL, VEL_TO_BASE, BASE_TO_DISP,
    GRAVITY, BASE_TO_ACCEL, DISP_TO_BASE, TIME_UNIFORMITY_TOLERANCE
)
from tkinter import messagebox

# ────────────────────────────────────────────────────────────────
# İsteğe bağlı SciPy bileşenleri
# ────────────────────────────────────────────────────────────────
try:
    from scipy import signal, integrate
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    signal = integrate = None

class DataProcessor:
    """Veri işleme ve deprem kaydı değerlendirme sınıfı"""

    # ────────────────────────────────
    # Kurulum
    # ────────────────────────────────
    def __init__(self):
        self.data_loader = None

    # ────────────────────────────────
    # Genel veri işleme (örnek)
    # ────────────────────────────────
    def process_data(self, data: pd.DataFrame) -> pd.DataFrame:
        return data.copy()

    # ────────────────────────────────
    # Kaydı okuma ve zaman serileri üretme
    # ────────────────────────────────
    def process_earthquake_record(
            self,
            file_path: str,
            params: Dict
        ) -> Dict:
        """
        Deprem kaydını işler; ivme, hız ve yerdeğiştirme serilerini üretir.
        Baseline correction ve filtering kaldırıldı.
        """

        try:
            # 1. Diyalog parametrelerini oku
            first_line     = int(params.get('first_line', 6)) - 1
            last_line      = int(params.get('last_line', -1))
            time_step      = float(params.get('time_step', 0.01))
            scaling_factor = float(params.get('scaling_factor', 1.0))
            format_type    = params.get('format', 'single_accel')
            accel_column   = int(params.get('accel_column', 2)) - 1
            time_column    = int(params.get('time_column', 1)) - 1
            frequency      = int(params.get('frequency', 1))
            initial_skip   = int(params.get('initial_skip', 0))

            accel_unit        = params.get('accel_unit', 'g')
            velocity_unit     = params.get('velocity_unit', 'cm/s')
            displacement_unit = params.get('displacement_unit', 'cm')

            # 2. Dosyayı oku
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            data_lines = lines[first_line:] if last_line == -1 else lines[first_line:last_line]

            # 3. İvme sütununu parse et
            accel_dict = self._parse_acceleration_data(
                data_lines, format_type, accel_column, time_column,
                frequency, initial_skip, scaling_factor
            )

            # 4. Zaman vektörü
            if format_type == 'time_accel' and 'time' in accel_dict:
                time_array = np.asarray(accel_dict['time'], dtype=float)
                if len(time_array) > 1:
                    # Zaman serisi doğrulama ve dt kestirimi
                    diffs = np.diff(time_array)
                    # Monotonluk kontrolü
                    if not np.all(diffs > 0):
                        raise ValueError("Zaman verisi monoton artan değil")

                    # Medyan aralığı ve bağıl sapmalar
                    median_dt = float(np.median(diffs))
                    if median_dt <= 0:
                        raise ValueError("Zaman aralığı sıfır veya negatif")

                    rel_dev = np.abs(diffs - median_dt) / median_dt
                    max_rel = float(np.max(rel_dev))

                    if max_rel <= TIME_UNIFORMITY_TOLERANCE:
                        # Kabul edilebilir oranda uniform – ortalama dt al
                        time_step = float(np.mean(diffs))
                    else:
                        # Aykırı farklar var – uyarı ver ve yeniden örnekleme uygula
                        print(f"⚠️ Zaman aralıkları uniform değil (max sapma: {max_rel:.3%}). Yeniden örnekleme uygulanacak.")
                        # Hedef düzenli eksen
                        n_pts = len(time_array)
                        t0 = time_array[0]
                        t_end = time_array[-1]
                        uniform_time = np.linspace(t0, t_end, n_pts)
                        time_step = float((t_end - t0) / (n_pts - 1)) if n_pts > 1 else median_dt

                        # İvme serisini de yeniden örnekle (lineer enterpolasyon)
                        accel_vals = np.asarray(accel_dict['acceleration'], dtype=float)
                        if len(accel_vals) != n_pts:
                            raise ValueError("Zaman ve ivme dizileri farklı uzunlukta")
                        accel_resampled = np.interp(uniform_time, time_array, accel_vals)
                        accel_dict['acceleration'] = accel_resampled.tolist()
                        time_array = uniform_time
            else:
                # AT2 formatından DT bilgisi geldi mi kontrol et
                if hasattr(self, '_at2_dt') and self._at2_dt:
                    time_step = self._at2_dt
                    print(f"🕐 AT2 dosyasından DT kullanılıyor: {time_step} saniye")
                    # AT2 DT bilgisini temizle
                    delattr(self, '_at2_dt')
                # ESM formatından DT bilgisi geldi mi kontrol et
                elif hasattr(self, '_esm_dt') and self._esm_dt:
                    time_step = self._esm_dt
                    print(f"🕐 ESM dosyasından SAMPLING_INTERVAL_S kullanılıyor: {time_step} saniye")
                    # ESM DT bilgisini temizle
                    delattr(self, '_esm_dt')
                
                n_pts      = len(accel_dict['acceleration'])
                time_array = np.arange(0, n_pts * time_step, time_step)[:n_pts]

            accel_array = np.asarray(accel_dict['acceleration'], dtype=float)

            # Kaynaktan gelen birime göre otomatik dönüştürme (ESM/AT2)
            source_units_code = getattr(self, '_units_code', None)
            detected_format = getattr(self, '_detected_format', None)
            if accel_array.size > 0 and source_units_code:
                if detected_format == 'AT2' or format_type in ['esm', 'peer_nga']:
                    try:
                        accel_array = self._convert_units_array('acceleration', accel_array, source_units_code, accel_unit)
                        print(f"🔁 İvme birimleri dönüştürüldü: {source_units_code} → {accel_unit}")
                    except Exception as conv_err:
                        print(f"⚠️ İvme birimi dönüştürülemedi ({source_units_code}→{accel_unit}): {conv_err}")

            # 5. Hız verisi - tespit edilen format tipine göre işle
            detected_format = getattr(self, '_detected_format', None)
            velocity_file_path = params.get('velocity_file_path')
            
            if detected_format == 'VT2':
                # Ana dosya zaten hız kaydı
                print("📊 Ana dosya VT2 formatında (hız kaydı) - doğrudan kullanılıyor")
                # VT2 dosyasındaki veri aslında hız; birimini normalize et
                src_code = getattr(self, '_units_code', None)
                if src_code:
                    try:
                        velocity_array = self._convert_units_array('velocity', accel_array, src_code, velocity_unit)
                        print(f"🔁 Hız birimleri dönüştürüldü: {src_code} → {velocity_unit}")
                    except Exception as conv_err:
                        print(f"⚠️ Hız birimi dönüştürülemedi ({src_code}→{velocity_unit}): {conv_err}")
                        velocity_array = accel_array
                else:
                    velocity_array = accel_array
                print("ℹ️ PEER NGA formatı - Sadece hız verisi mevcut (ayrı AT2 dosyası gerekli)")
                # İvme array'ini boş bırak - sadece hız verisi kullanılacak
                accel_array = np.array([])
            elif velocity_file_path:
                print(f"📁 Hız kaydı ek dosyadan yükleniyor: {velocity_file_path}")
                velocity_array = self._load_additional_file(velocity_file_path, params, velocity_unit)
            else:
                if accel_array.size > 0:
                    print("🔄 Hız kaydı ivmeden hesaplanıyor (integrasyon)")
                    velocity_array = self._integrate_acceleration_simple(
                        accel_array, time_step, accel_unit, velocity_unit
                    )
                else:
                    msg = "Hız kaydı hesaplanamadı: ivme verisi mevcut değil."
                    print(f"⚠️ {msg}")
                    try:
                        messagebox.showwarning("Eksik veri", msg)
                    except Exception:
                        pass
                    velocity_array = np.array([])

            # 6. Yerdeğiştirme verisi - tespit edilen format tipine göre işle
            displacement_file_path = params.get('displacement_file_path')
            
            if detected_format == 'DT2':
                # Ana dosya zaten yerdeğiştirme kaydı
                print("📊 Ana dosya DT2 formatında (yerdeğiştirme kaydı) - doğrudan kullanılıyor")
                # DT2 dosyasındaki veri aslında yerdeğiştirme; birimini normalize et
                src_code = getattr(self, '_units_code', None)
                if src_code:
                    try:
                        displacement_array = self._convert_units_array('displacement', accel_array, src_code, displacement_unit)
                        print(f"🔁 Yerdeğiştirme birimleri dönüştürüldü: {src_code} → {displacement_unit}")
                    except Exception as conv_err:
                        print(f"⚠️ Yerdeğiştirme birimi dönüştürülemedi ({src_code}→{displacement_unit}): {conv_err}")
                        displacement_array = accel_array
                else:
                    displacement_array = accel_array
                print("ℹ️ PEER NGA formatı - Sadece yerdeğiştirme verisi mevcut (ayrı AT2/VT2 dosyaları gerekli)")
                # Hız ve ivme array'lerini boş bırak - sadece yerdeğiştirme verisi kullanılacak
                velocity_array = np.array([])
                accel_array = np.array([])
            elif displacement_file_path:
                print(f"📁 Yerdeğiştirme kaydı ek dosyadan yükleniyor: {displacement_file_path}")
                displacement_array = self._load_additional_file(displacement_file_path, params, displacement_unit)
            else:
                if velocity_array.size > 0:
                    print("🔄 Yerdeğiştirme kaydı hızdan hesaplanıyor (integrasyon)")
                    displacement_array = self._integrate_velocity_simple(
                        velocity_array, time_step, velocity_unit, displacement_unit
                    )
                else:
                    msg = "Yerdeğiştirme kaydı hesaplanamadı: hız verisi mevcut değil."
                    print(f"⚠️ {msg}")
                    try:
                        messagebox.showwarning("Eksik veri", msg)
                    except Exception:
                        pass
                    displacement_array = np.array([])
                
            # Tespit edilen format bilgisini al ve temizle
            detected_format = getattr(self, '_detected_format', None)
            earthquake_name = getattr(self, '_earthquake_name', None)
            units_info = getattr(self, '_units_info', None)
            station = getattr(self, '_station', None)
            component = getattr(self, '_component', None)
            azimuth_deg = getattr(self, '_azimuth_deg', None)
            npts_meta = getattr(self, '_npts', None)
            
            if hasattr(self, '_detected_format'):
                delattr(self, '_detected_format')
            if hasattr(self, '_earthquake_name'):
                delattr(self, '_earthquake_name')
            if hasattr(self, '_units_info'):
                delattr(self, '_units_info')
            if hasattr(self, '_units_code'):
                delattr(self, '_units_code')
            for _attr in ('_station','_component','_azimuth_deg','_npts'):
                if hasattr(self, _attr):
                    try:
                        delattr(self, _attr)
                    except Exception:
                        pass

            # 7. Özet
            accel_status = f"{len(accel_array):,} nokta" if len(accel_array) > 0 else "Mevcut değil"
            velocity_status = f"{len(velocity_array):,} nokta" if len(velocity_array) > 0 else "Mevcut değil"
            displacement_status = f"{len(displacement_array):,} nokta" if len(displacement_array) > 0 else "Mevcut değil"
            
            print(
                "📊 Hesaplama tamamlandı:"
                f"\n   • İvme ({accel_unit}): {accel_status}"
                f"\n   • Hız ({velocity_unit}): {velocity_status}"
                f"\n   • Yerdeğiştirme ({displacement_unit}): {displacement_status}"
                f"\n   • Zaman noktası: {len(time_array):,}"
                f"\n   • Süre: {time_array[-1]:.3f} s"
            )

            result = {
                'time':          time_array,
                'acceleration':  accel_array,
                'velocity':      velocity_array,
                'displacement':  displacement_array,
                'params':        params,
                'file_path':     file_path,
                'units': {
                    'time':          's',
                    'acceleration':  accel_unit,
                    'velocity':      velocity_unit,
                    'displacement':  displacement_unit
                }
            }
            
            # PEER NGA format bilgilerini ekle
            if detected_format:
                result['format_type'] = detected_format
            if earthquake_name:
                result['earthquake_name'] = earthquake_name
            if units_info:
                result['original_units_info'] = units_info
            # Header meta
            if station:
                result['station'] = station
            if component:
                result['component'] = component
            if azimuth_deg is not None:
                result['azimuth_deg'] = azimuth_deg
            if npts_meta is not None:
                result['npts'] = npts_meta
                
            return result

        except Exception as e:
            raise ValueError(f"Deprem kaydı işleme hatası: {e}")

    # ────────────────────────────────
    # 3.a  İvme satırlarını okuma
    # ────────────────────────────────
    def _parse_acceleration_data(
            self, lines: List[str], format_type: str,
            accel_col: int, time_col: int,
            frequency: int, initial_skip: int,
            scaling_factor: float
        ) -> Dict:
        """Desteklenen tüm formatlarda ivme sütununu çıkarır"""
        acceleration, time_data = [], []

        try:
            if format_type == 'single_accel':
                # Hızlı blok okuma dene; olmazsa satır satır geri dön
                try:
                    joined = '\n'.join(lines)
                    joined = joined.replace('D', 'E').replace('d', 'E')
                    arr = np.fromstring(joined, sep=' ', dtype=float)
                    acceleration = (arr * scaling_factor).tolist()
                except Exception:
                    for line in lines:
                        vals = line.strip().split()
                        if len(vals) > accel_col:
                            acceleration.append(float(vals[accel_col]) * scaling_factor)

            elif format_type == 'time_accel':
                for line in lines:
                    vals = line.strip().split()
                    if len(vals) > max(accel_col, time_col):
                        time_data.append(float(vals[time_col]))
                        acceleration.append(float(vals[accel_col]) * scaling_factor)

            elif format_type == 'multi_accel':
                global_idx = 0
                for line in lines:
                    vals = line.strip().split()
                    for val in vals[accel_col:]:
                        if global_idx >= initial_skip and \
                           ((global_idx - initial_skip) % frequency == 0):
                            acceleration.append(float(val) * scaling_factor)
                        global_idx += 1

            elif format_type in ['esm', 'peer_nga']:
                # AT2/VT2/DT2 formatı kontrolü
                if self._is_at2_format(lines):
                    result_data = self._parse_at2_format(lines, scaling_factor)
                    if isinstance(result_data, dict):
                        acceleration = result_data['acceleration']
                        # AT2/VT2/DT2'den gelen DT bilgisini sakla
                        if 'dt' in result_data:
                            self._at2_dt = result_data['dt']
                        # Format tipini sakla
                        if 'format_type' in result_data:
                            self._detected_format = result_data['format_type']
                        # Deprem adını sakla
                        if 'earthquake_name' in result_data:
                            self._earthquake_name = result_data['earthquake_name']
                        # Birim bilgisini sakla
                        if 'units_info' in result_data:
                            self._units_info = result_data['units_info']
                    else:
                        acceleration = result_data
                # ESM formatı kontrolü
                elif self._is_esm_format(lines):
                    result_data = self._parse_esm_format(lines, scaling_factor)
                    if isinstance(result_data, dict):
                        acceleration = result_data['acceleration']
                        # ESM'den gelen DT bilgisini sakla
                        if 'dt' in result_data:
                            self._esm_dt = result_data['dt']
                    else:
                        acceleration = result_data
                else:
                    # Standart PEER NGA formatı - hızlı blok parsing
                    try:
                        joined = '\n'.join(lines)
                        joined = joined.replace('D', 'E').replace('d', 'E')
                        arr = np.fromstring(joined, sep=' ', dtype=float)
                        acceleration = (arr * scaling_factor).tolist()
                    except Exception:
                        # Güvenli geri dönüş
                        for line in lines:
                            if not line.strip():
                                continue
                            try:
                                values = line.strip().split()
                                for val_str in values:
                                    try:
                                        val = float(val_str) * scaling_factor
                                        acceleration.append(val)
                                    except ValueError:
                                        continue
                            except (ValueError, IndexError):
                                continue

        except Exception as e:
            raise ValueError(f"Veri parsing hatası: {e}")

        result = {'acceleration': acceleration}
        if time_data:
            result['time'] = time_data
        return result

    # ────────────────────────────────
    # 3.b  Basit İvme → Hız entegrasyonu
    # ────────────────────────────────
    def _integrate_acceleration_simple(
            self, accel: np.ndarray, dt: float,
            accel_unit: str, velocity_unit: str
        ) -> np.ndarray:
        """
        Basit sayısal integrasyon (baseline correction ve filtering olmadan)
        """
        # 1. Sayısal entegrasyon
        if SCIPY_AVAILABLE:
            velocity = integrate.cumulative_trapezoid(accel, dx=dt, initial=0.0)
        else:
            velocity = np.concatenate((
                [0.0],
                np.cumsum((accel[:-1] + accel[1:]) * dt * 0.5)
            ))

        # 2. Birim dönüştürme (merkezi sabitler üzerinden)
        # accel_unit → m/s² → (×dt entegrasyon sonrası) → m/s → hedef hız birimi
        accel_to_base = ACCEL_TO_BASE.get(accel_unit, 1.0)
        base_to_vel = BASE_TO_VEL.get(velocity_unit, 1.0)
        velocity *= (accel_to_base * base_to_vel)

        print(f"🔄 İvme→Hız dönüştürme tamam: {accel_unit}·s → {velocity_unit}")
        return velocity

    # ────────────────────────────────
    # 3.c  Basit Hız → Yerdeğiştirme entegrasyonu
    # ────────────────────────────────
    def _integrate_velocity_simple(
            self, velocity: np.ndarray, dt: float,
            velocity_unit: str, displacement_unit: str
        ) -> np.ndarray:
        """
        Basit sayısal integrasyon (baseline correction olmadan)
        """
        # 1. Entegrasyon
        if SCIPY_AVAILABLE:
            displacement = integrate.cumulative_trapezoid(velocity, dx=dt, initial=0.0)
        else:
            displacement = np.concatenate((
                [0.0],
                np.cumsum((velocity[:-1] + velocity[1:]) * dt * 0.5)
            ))

        # 2. Birim dönüştürme (merkezi sabitler üzerinden)
        # velocity_unit → m/s → entegrasyonla m → hedef yerdeğiştirme birimi
        vel_to_base = VEL_TO_BASE.get(velocity_unit, 1.0)
        base_to_disp = BASE_TO_DISP.get(displacement_unit, 1.0)
        displacement *= (vel_to_base * base_to_disp)

        print(f"🔄 Hız→Yerdeğiştirme dönüştürme tamam: {velocity_unit}·s → {displacement_unit}")
        return displacement

    def _differentiate_velocity_simple(
            self, velocity: np.ndarray, dt: float,
            velocity_unit: str, accel_unit: str
        ) -> np.ndarray:
        """
        Hızdan ivme hesaplama (basit türev alma)
        """
        # Sayısal türev alma
        acceleration = np.gradient(velocity, dt)
        
        # Birim dönüştürme (merkezi sabitler üzerinden)
        vel_to_base = VEL_TO_BASE.get(velocity_unit, 1.0)
        base_to_accel = BASE_TO_ACCEL.get(accel_unit, 1.0)
        acceleration *= (vel_to_base * base_to_accel)
        print(f"🔄 Hız→İvme dönüştürme tamam: {velocity_unit}/s → {accel_unit}")
        return acceleration
    
    def _differentiate_displacement_simple(
            self, displacement: np.ndarray, dt: float,
            displacement_unit: str, velocity_unit: str
        ) -> np.ndarray:
        """
        Yerdeğiştirmeden hız hesaplama (basit türev alma)
        """
        # Sayısal türev alma
        velocity = np.gradient(displacement, dt)
        
        # Birim dönüştürme (merkezi sabitler üzerinden)
        disp_to_base = DISP_TO_BASE.get(displacement_unit, 1.0)
        base_to_vel = BASE_TO_VEL.get(velocity_unit, 1.0)
        velocity *= (disp_to_base * base_to_vel)
        print(f"🔄 Yerdeğiştirme→Hız dönüştürme tamam: {displacement_unit}/s → {velocity_unit}")
        return velocity

    def _is_at2_format(self, lines):
        """
        AT2/VT2/DT2 formatı olup olmadığını kontrol eder
        """
        if len(lines) < 4:
            return False
        
        # İlk satırda "PEER NGA" kontrolü
        if "PEER NGA" in lines[0].upper():
            return True
        
        # 4. satırda "NPTS=" ve "DT=" kontrolü
        if len(lines) >= 4 and "NPTS=" in lines[3] and "DT=" in lines[3]:
            return True
            
        return False
    
    def _parse_at2_format(self, lines, scaling_factor):
        """
        AT2/VT2/DT2 formatındaki veriyi parse eder
        
        AT2/VT2/DT2 Format:
        - Satır 1: PEER NGA başlık
        - Satır 2: Deprem bilgisi
        - Satır 3: Birim bilgisi (ACCELERATION/VELOCITY/DISPLACEMENT TIME SERIES IN UNITS OF...)
        - Satır 4: NPTS= xxxx, DT= xxxx SEC,
        - Satır 5+: Her satırda 5 adet değer (E formatında)
        """
        acceleration = []
        
        try:
            # 4. satırdan NPTS ve DT değerlerini al
            header_line = lines[3]
            
            # NPTS değeri
            npts_start = header_line.find("NPTS=") + 5
            npts_end = header_line.find(",", npts_start)
            npts = int(header_line[npts_start:npts_end].strip())
            
            # DT değeri
            dt_start = header_line.find("DT=") + 3
            dt_end = header_line.find("SEC", dt_start)
            dt = float(header_line[dt_start:dt_end].strip())
            
            # Deprem adını çıkar (2. satırdan, ilk virgüle kadar)
            earthquake_name = "Bilinmeyen Deprem"
            if len(lines) >= 2:
                name_line = lines[1].strip()
                if ',' in name_line:
                    earthquake_name = name_line.split(',')[0].strip()
            
            # Birim bilgisini çıkar (3. satırdan)
            units_info = "Bilinmeyen Birim"
            format_type = "AT2"  # Varsayılan
            if len(lines) >= 3:
                units_line = lines[2].strip()
                units_info = units_line
                
                # Format tipini tespit et
                units_upper = units_line.upper()
                if "VELOCITY" in units_upper:
                    format_type = "VT2"
                elif "DISPLACEMENT" in units_upper:
                    format_type = "DT2"
                elif "ACCELERATION" in units_upper:
                    format_type = "AT2"
                    
                # Birim bilgisini çıkar (UNITS OF sonrasında)
                if "UNITS OF" in units_upper:
                    units_start = units_upper.find("UNITS OF") + 8
                    extracted_unit = units_line[units_start:].strip()
                    if extracted_unit:
                        units_info = extracted_unit
                        # Kaynak birim kodunu kaba eşle
                        # Daha spesifik anahtarlar önce, genel anahtarlar sonra (örn. 'CM' → 'M' çakışmasını engellemek için)
                        unit_map = {
                            # İvme
                            'CM/S^2': 'cm/s²', 'CM/S²': 'cm/s²', 'MM/S^2': 'mm/s²', 'MM/S²': 'mm/s²', 'M/S^2': 'm/s²', 'M/S²': 'm/s²', 'G': 'g',
                            # Hız
                            'CM/S': 'cm/s', 'MM/S': 'mm/s', 'KM/H': 'km/h', 'M/S': 'm/s',
                            # Yerdeğiştirme
                            'CM': 'cm', 'MM': 'mm', 'UM': 'μm', 'KM': 'km', 'M': 'm'
                        }
                        key = extracted_unit.strip().upper().replace('²','^2').replace('^2','^2')
                        # normalize anahtarlar
                        key = key.replace('/S^2','/S^2').replace('MICROMETER','UM').replace('MICROMETRE','UM')
                        for k,v in unit_map.items():
                            if k in key:
                                self._units_code = v
                                break
            
            print(f"📊 {format_type} formatı tespit edildi:")
            print(f"   - Deprem: {earthquake_name}")
            print(f"   - Birim: {units_info}")
            print(f"   - NPTS: {npts}, DT: {dt} saniye")
            # İstasyon/bileşen/azimut çıkarımı (en fazla ilk 10 satır taranır)
            station = None
            component = None
            azimuth_deg = None
            try:
                header_block = "\n".join([ln.strip() for ln in lines[:10]])
                import re as _re
                # Station
                m_sta = _re.search(r"STATION\s*[:=\-]?\s*([A-Za-z0-9 _\-\.\/]+)", header_block, flags=_re.IGNORECASE)
                if m_sta:
                    station = m_sta.group(1).strip()
                # Component/channel
                m_comp = _re.search(r"COMP(ONENT)?\s*[:=\-]?\s*([A-Za-z0-9 _\-\.\/]+)", header_block, flags=_re.IGNORECASE)
                if m_comp:
                    component = m_comp.group(2).strip()
                # Azimuth in degrees
                m_az = _re.search(r"AZ(IMUTH)?\s*[:=\-]?\s*([\-+]?\d+(?:\.\d+)?)\s*DEG", header_block, flags=_re.IGNORECASE)
                if m_az:
                    try:
                        azimuth_deg = float(m_az.group(2))
                    except Exception:
                        azimuth_deg = None
            except Exception:
                pass
            
            # 5. satırdan itibaren veri okuma
            data_lines = lines[4:]
            
            for line in data_lines:
                if not line.strip():
                    continue
                    
                # Her satırdaki değerleri ayır
                values = line.strip().split()
                for val_str in values:
                    try:
                        # E formatını (örn: -.2098335E-03) float'a çevir
                        val = float(val_str) * scaling_factor
                        acceleration.append(val)
                        
                        # NPTS kadar veri aldıysak dur
                        if len(acceleration) >= npts:
                            break
                    except ValueError:
                        continue
                
                # NPTS kadar veri aldıysak dur
                if len(acceleration) >= npts:
                    break
            
            print(f"✅ {format_type} veri parsing tamamlandı: {len(acceleration)} değer okundu")
            
            # Tüm bilgileri döndür
            # Bellek üzerinde sakla (process_earthquake_record sonucuna da taşımak için)
            try:
                self._station = station
                self._component = component
                self._azimuth_deg = azimuth_deg
                self._npts = npts
            except Exception:
                pass

            return {
                'acceleration': acceleration,
                'dt': dt,
                'npts': npts,
                'format_type': format_type,
                'earthquake_name': earthquake_name,
                'units_info': units_info,
                'station': station,
                'component': component,
                'azimuth_deg': azimuth_deg,
            }
            
        except Exception as e:
            print(f"❌ AT2 parsing hatası: {e}")
            # Hata durumunda standart parsing'e geri dön - satır satır, soldan sağa
            acceleration = []
            for line in lines[4:]:  # 5. satırdan itibaren
                if not line.strip():
                    continue
                try:
                    # Her satırdaki tüm değerleri al (soldan sağa)
                    values = line.strip().split()
                    for val_str in values:
                        try:
                            val = float(val_str) * scaling_factor
                            acceleration.append(val)
                        except ValueError:
                            continue
                except (ValueError, IndexError):
                    continue
            return acceleration

    def _is_esm_format(self, lines):
        """
        ESM formatı olup olmadığını kontrol eder
        """
        if len(lines) < 30:
            return False
        
        # ESM formatının karakteristik başlık alanlarını kontrol et
        esm_keywords = [
            'EVENT_NAME:', 'EVENT_ID:', 'SAMPLING_INTERVAL_S:', 
            'NDATA:', 'UNITS:', 'STREAM:'
        ]
        
        found_keywords = 0
        for i, line in enumerate(lines[:65]):  # İlk 65 satırda kontrol et
            for keyword in esm_keywords:
                if keyword in line:
                    found_keywords += 1
                    break
        
        # En az 4 anahtar kelime bulunursa ESM formatı
        return found_keywords >= 4
    
    def _parse_esm_format(self, lines, scaling_factor):
        """
        ESM formatındaki veriyi parse eder
        
        ESM Format:
        - İlk ~64 satır: Metadata (EVENT_NAME, SAMPLING_INTERVAL_S, NDATA, UNITS, vb.)
        - Sonraki satırlar: Her satırda tek ivme değeri
        """
        acceleration = []
        sampling_interval = None
        ndata = None
        units = None
        
        try:
            # Metadata bölümünü parse et
            data_start_line = 65  # Varsayılan veri başlangıcı
            
            for i, line in enumerate(lines[:100]):  # İlk 100 satırda metadata ara
                line = line.strip()
                
                # SAMPLING_INTERVAL_S değerini al
                if line.startswith('SAMPLING_INTERVAL_S:'):
                    try:
                        sampling_interval = float(line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass
                
                # NDATA değerini al
                elif line.startswith('NDATA:'):
                    try:
                        ndata = int(line.split(':')[1].strip())
                    except (ValueError, IndexError):
                        pass
                
                # UNITS bilgisini al
                elif line.startswith('UNITS:'):
                    try:
                        units = line.split(':')[1].strip()
                    except IndexError:
                        pass
                
                # Veri başlangıcını tespit et (ilk sayısal değer)
                elif line and not ':' in line:
                    try:
                        float(line)
                        data_start_line = i
                        break
                    except ValueError:
                        continue
            
            print(f"📊 ESM formatı tespit edildi:")
            print(f"   - NDATA: {ndata}")
            print(f"   - SAMPLING_INTERVAL_S: {sampling_interval}")
            print(f"   - UNITS: {units}")
            print(f"   - Veri başlangıcı: Satır {data_start_line + 1}")
            
            # Veri bölümünü parse et
            data_lines = lines[data_start_line:]
            
            for line in data_lines:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    # Her satırda tek değer
                    val = float(line) * scaling_factor
                    acceleration.append(val)
                    
                    # NDATA kadar veri aldıysak dur
                    if ndata and len(acceleration) >= ndata:
                        break
                except ValueError:
                    continue
            
            print(f"✅ ESM veri parsing tamamlandı: {len(acceleration)} değer okundu")
            
            # Hem acceleration hem de dt bilgisini döndür
            result = {'acceleration': acceleration}
            if sampling_interval:
                result['dt'] = sampling_interval
            if ndata:
                result['ndata'] = ndata
            if units:
                result['units'] = units
                # Kaynak birim kodunu kaba eşle
                unit_upper = units.strip().upper()
                # Daha spesifik anahtarlar önce, genel anahtarlar sonra
                unit_map = {
                    # İvme
                    'CM/S^2': 'cm/s²', 'CM/S²': 'cm/s²', 'MM/S^2': 'mm/s²', 'MM/S²': 'mm/s²', 'M/S^2': 'm/s²', 'M/S²': 'm/s²', 'G': 'g',
                    # Hız
                    'CM/S': 'cm/s', 'MM/S': 'mm/s', 'KM/H': 'km/h', 'M/S': 'm/s',
                    # Yerdeğiştirme
                    'CM': 'cm', 'MM': 'mm', 'UM': 'μm', 'KM': 'km', 'M': 'm'
                }
                for k,v in unit_map.items():
                    if k in unit_upper:
                        self._units_code = v
                        break
                
            return result
            
        except Exception as e:
            print(f"❌ ESM parsing hatası: {e}")
            # Hata durumunda standart parsing'e geri dön - satır satır, soldan sağa
            acceleration = []
            for line in lines[65:]:  # 65. satırdan itibaren
                line = line.strip()
                if not line or ':' in line:
                    continue
                try:
                    # Her satırdaki tüm değerleri al (soldan sağa)
                    values = line.split()
                    for val_str in values:
                        try:
                            val = float(val_str) * scaling_factor
                            acceleration.append(val)
                        except ValueError:
                            continue
                except (ValueError, IndexError):
                    continue
            return acceleration

    # ────────────────────────────────
    # 3.e  Birim dönüştürme faktörleri
    # ────────────────────────────────
    def _get_accel_to_velocity_conversion(self, accel_unit: str, velocity_unit: str) -> float:
        # Geriye uyumluluk için bırakıldı; yeni sabitleri kullanır
        return ACCEL_TO_BASE.get(accel_unit, 1.0) * BASE_TO_VEL.get(velocity_unit, 1.0)

    def _get_velocity_to_displacement_conversion(self, velocity_unit: str, displacement_unit: str) -> float:
        # Geriye uyumluluk için bırakıldı; yeni sabitleri kullanır
        return VEL_TO_BASE.get(velocity_unit, 1.0) * BASE_TO_DISP.get(displacement_unit, 1.0)
    
    def _get_velocity_to_accel_conversion(self, velocity_unit: str, accel_unit: str) -> float:
        """Hız biriminden ivme birimine dönüştürme faktörü (türev için)"""
        vel_factor = VEL_TO_BASE.get(velocity_unit, 1.0)
        accel_factor = BASE_TO_ACCEL.get(accel_unit, 1.0)
        return vel_factor * accel_factor
    
    def _get_displacement_to_velocity_conversion(self, displacement_unit: str, velocity_unit: str) -> float:
        """Yerdeğiştirme biriminden hız birimine dönüştürme faktörü (türev için)"""
        disp_factor = DISP_TO_BASE.get(displacement_unit, 1.0)
        vel_factor = BASE_TO_VEL.get(velocity_unit, 1.0)
        return disp_factor * vel_factor

    # ────────────────────────────────
    # 4.  Zaman serisi istatistikleri
    # ────────────────────────────────
    def get_time_series_stats(self, data: Dict) -> Dict:
        """
        Zaman serisi istatistiklerini hesaplar (StatsPanel ile uyumlu format)
        
        Args:
            data: İşlenmiş deprem verisi dict'i
            
        Returns:
            Dict: PGA, PGV, PGD, RMS, Arias Intensity, CAV, vb. istatistikler
        """
        try:
            # Giriş doğrulama
            if not data or not isinstance(data, dict):
                return {}

            # Ham dizileri al
            time_data = data.get('time')
            acceleration = data.get('acceleration')
            velocity = data.get('velocity')
            displacement = data.get('displacement')

            import numpy as np  # yerel import güvenlidir
            time_arr = np.asarray(time_data) if time_data is not None else np.asarray([])
            acc_arr = np.asarray(acceleration) if acceleration is not None else np.asarray([])

            # Minimum gereksinimler
            if time_arr.size < 2 or acc_arr.size == 0:
                return {}

            # Diğer diziler: yoksa ivme ile aynı uzunlukta sıfırlar
            if velocity is not None and len(velocity) > 0:
                vel_arr = np.asarray(velocity)
            else:
                vel_arr = np.zeros_like(acc_arr, dtype=float)

            if displacement is not None and len(displacement) > 0:
                disp_arr = np.asarray(displacement)
            else:
                disp_arr = np.zeros_like(acc_arr, dtype=float)

            # Birim bilgileri
            accel_unit = data.get('accel_unit', 'g')
            velocity_unit = data.get('velocity_unit', 'cm/s')
            displacement_unit = data.get('displacement_unit', 'cm')

            # EarthquakeStats ile tüm istatistikleri hesapla
            from ..calculations.earthquake_stats import EarthquakeStats
            stats = EarthquakeStats.calculate_all_stats(
                time_data=time_arr,
                acceleration=acc_arr,
                velocity=vel_arr,
                displacement=disp_arr,
                accel_unit=accel_unit,
                velocity_unit=velocity_unit,
                displacement_unit=displacement_unit
            )
            # UI sözlük bekliyor; dataclass'ı uyumlu sözlüğe çevir
            try:
                from dataclasses import asdict
                stats_dict = asdict(stats)

                def _map_peak(prefix_key: str, peak_obj: dict) -> dict:
                    return {
                        f"{prefix_key}_abs": peak_obj.get("peak_abs"),
                        f"{prefix_key}_pos": peak_obj.get("peak_pos"),
                        f"{prefix_key}_neg": peak_obj.get("peak_neg"),
                        # Tepe değer zamanları (s)
                        "t_peak_abs": peak_obj.get("t_peak_abs"),
                        "t_peak_pos": peak_obj.get("t_peak_pos"),
                        "t_peak_neg": peak_obj.get("t_peak_neg"),
                        "unit": peak_obj.get("unit"),
                    }

                ui_result = {
                    "pga": _map_peak("pga", stats_dict.get("pga", {})),
                    "pgv": _map_peak("pgv", stats_dict.get("pgv", {})),
                    "pgd": _map_peak("pgd", stats_dict.get("pgd", {})),
                    "rms": stats_dict.get("rms", {}),
                    "arias_intensity": stats_dict.get("arias_intensity", {}),
                    "arias_a95": stats_dict.get("arias_a95", {}),
                    "significant_duration_5_95": stats_dict.get("significant_duration_5_95", {}),
                    "significant_duration_5_75": stats_dict.get("significant_duration_5_75", {}),
                    "significant_duration_2_5_97_5": stats_dict.get("significant_duration_2_5_97_5", {}),
                    "cav": {
                        "cav": stats_dict.get("cav", {}).get("value"),
                        "unit": stats_dict.get("cav", {}).get("unit", "g·s"),
                    },
                    "cavstd": {
                        "cav": stats_dict.get("cavstd", {}).get("value"),
                        "unit": stats_dict.get("cavstd", {}).get("unit", "g·s"),
                    },
                    "record_info": stats_dict.get("record_info", {}),
                    "sampling_info": stats_dict.get("sampling_info", {}),
                }

                rec = ui_result.get("record_info", {})
                ui_result["duration"] = rec.get("length")
                ui_result["num_points"] = rec.get("data_points")
                ui_result["acceleration"] = {
                    "peak": stats_dict.get("pga", {}).get("peak_abs"),
                    "unit": ui_result.get("pga", {}).get("unit", accel_unit),
                }
                ui_result["velocity"] = {
                    "peak": stats_dict.get("pgv", {}).get("peak_abs"),
                    "unit": ui_result.get("pgv", {}).get("unit", velocity_unit),
                }
                ui_result["displacement"] = {
                    "peak": stats_dict.get("pgd", {}).get("peak_abs"),
                    "unit": ui_result.get("pgd", {}).get("unit", displacement_unit),
                }

                return ui_result
            except Exception:
                return stats

        except Exception as e:
            print(f"❌ İstatistik hesaplama hatası: {e}")
            import traceback
            traceback.print_exc()
            return {}

    # ────────────────────────────────
    # 5.  Birim dönüştürme
    # ────────────────────────────────
    def convert_units(self, data: Dict, old_units: Dict, new_units: Dict) -> Dict:
        converted = data.copy()
        try:
            # İvme
            o_acc, n_acc = old_units.get('acceleration'), new_units.get('acceleration')
            if o_acc and n_acc and o_acc != n_acc:
                f = self._get_acceleration_conversion_factor(o_acc, n_acc)
                converted['acceleration'] = np.asarray(data['acceleration']) * f
                print(f"🔄 İvme: {o_acc} → {n_acc} (×{f})")

            # Hız
            o_vel, n_vel = old_units.get('velocity'), new_units.get('velocity')
            if o_vel and n_vel and o_vel != n_vel:
                f = self._get_velocity_conversion_factor(o_vel, n_vel)
                converted['velocity'] = np.asarray(data['velocity']) * f
                print(f"🔄 Hız: {o_vel} → {n_vel} (×{f})")

            # Yerdeğiştirme
            o_disp, n_disp = old_units.get('displacement'), new_units.get('displacement')
            if o_disp and n_disp and o_disp != n_disp:
                f = self._get_displacement_conversion_factor(o_disp, n_disp)
                converted['displacement'] = np.asarray(data['displacement']) * f
                print(f"🔄 Yerdeğiştirme: {o_disp} → {n_disp} (×{f})")

            converted['units'] = {
                'time':          's',
                'acceleration':  n_acc or o_acc,
                'velocity':      n_vel or o_vel,
                'displacement':  n_disp or o_disp
            }

        except Exception as e:
            print(f"❌ Birim dönüştürme hatası: {e}")
        return converted

    def _convert_units_array(self, kind: str, array: np.ndarray, source_code: str, target_code: str) -> np.ndarray:
        """Tek boyutlu diziyi birim kodlarına göre dönüştürür.
        kind: 'acceleration' | 'velocity' | 'displacement'
        """
        if source_code == target_code:
            return array
        if kind == 'acceleration':
            factor = ACCEL_TO_BASE.get(source_code, 1.0) * BASE_TO_ACCEL.get(target_code, 1.0)
        elif kind == 'velocity':
            factor = VEL_TO_BASE.get(source_code, 1.0) * BASE_TO_VEL.get(target_code, 1.0)
        elif kind == 'displacement':
            factor = DISP_TO_BASE.get(source_code, 1.0) * BASE_TO_DISP.get(target_code, 1.0)
        else:
            factor = 1.0
        return np.asarray(array) * factor

    def _get_acceleration_conversion_factor(self, from_unit: str, to_unit: str) -> float:
        acc2 = {'g': 9.81, 'm/s²': 1.0, 'cm/s²': 0.01, 'mm/s²': 0.001}
        return acc2.get(from_unit, 1.0) / acc2.get(to_unit, 1.0)

    def _get_velocity_conversion_factor(self, from_unit: str, to_unit: str) -> float:
        vel2 = {'m/s': 1.0, 'cm/s': 0.01, 'mm/s': 0.001, 'km/h': 1/3.6}
        return vel2.get(from_unit, 1.0) / vel2.get(to_unit, 1.0)

    def _get_displacement_conversion_factor(self, from_unit: str, to_unit: str) -> float:
        disp2 = {'m': 1.0, 'cm': 0.01, 'mm': 0.001, 'μm': 1e-6}
        return disp2.get(from_unit, 1.0) / disp2.get(to_unit, 1.0)

    # ────────────────────────────────
    # 6.  Harita‑tabanlı yardımcılar
    # ────────────────────────────────
    def get_parameters_for_location(self, lat, lon, earthquake_level):
        """
        AFAD TDTH grid verisinden, verilen koordinat i?in Ss ve S1 de?erlerini d?nd?r?r.

        IDW (metre bazl?, k=8, p=2) birincil y?ntemdir; DataLoader gerekirse
        bilinear ve en yak?n kom?u geri d?n??lerini otomatik y?netir.
        """
        if not hasattr(self.data_loader, 'is_data_loaded') or not self.data_loader.is_data_loaded():
            messagebox.showerror("Veri Hatasi", "Veri seti yuklenmemis.")
            return None, None

        try:
            results = self.data_loader.get_interpolated_values(
                lat,
                lon,
                earthquake_level,
                cols=["Ss", "S1"],
                k=8,
                power=2.0,
            )
            ss_val = results.get("Ss")
            s1_val = results.get("S1")

            if ss_val is None or s1_val is None:
                raise ValueError("Ss/S1 de?erleri hesaplanamad? (IDW/bilinear).")

            print(f"IDW AFAD Ss/S1 -> Ss={float(ss_val):.4f}, S1={float(s1_val):.4f}")
            return float(ss_val), float(s1_val)

        except Exception as e:
            messagebox.showerror("Veri Isleme Hatasi",
                                 f"Parametreler alinirken hata: {str(e)}")
            print(f"[ERR] get_parameters_for_location: {e}")
            return None, None

    def get_data_bounds(self):
        """Veri setindeki koordinat sınırlarını döndürür"""
        if not hasattr(self.data_loader, 'is_data_loaded') or not self.data_loader.is_data_loaded():
            return None
        df = self.data_loader.loaded_data
        return {"min_lat": df['Enlem'].min(), "max_lat": df['Enlem'].max(),
                "min_lon": df['Boylam'].min(), "max_lon": df['Boylam'].max()}

    def validate_coordinates(self, lat, lon):
        """Koordinatların veri seti sınırları içinde olup olmadığını kontrol eder"""
        bounds = self.get_data_bounds()
        if bounds is None: return False
        return (bounds["min_lat"] <= lat <= bounds["max_lat"] and
                bounds["min_lon"] <= lon <= bounds["max_lon"])

    def get_available_earthquake_levels(self):
        """Veri setinde mevcut deprem düzeylerini döndürür"""
        if not hasattr(self.data_loader, 'is_data_loaded') or not self.data_loader.is_data_loaded():
            return []
        df = self.data_loader.loaded_data
        ss_columns = [col for col in df.columns if col.startswith('Ss_')]
        return [col.replace('Ss_', '').replace('DD', 'DD-') for col in ss_columns]

    def _load_additional_file(self, file_path: str, params: Dict, target_unit: str) -> np.ndarray:
        """
        Ek dosyadan (hız veya yerdeğiştirme) veri yükler
        """
        try:
            scaling_factor = float(params.get('scaling_factor', 1.0))
            
            # Dosyayı oku
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Dosya formatını tespit et
            if self._is_at2_format(lines):
                # PEER NGA formatı (VT2/DT2) - satır satır, soldan sağa oku
                print(f"📊 PEER NGA formatı tespit edildi: {file_path}")
                result_data = self._parse_at2_format(lines, scaling_factor)
                if isinstance(result_data, dict):
                    data_array = np.asarray(result_data['acceleration'], dtype=float)
                    # Kaynak birim kodu varsa normalize et
                    src_code = getattr(self, '_units_code', None)
                    if src_code:
                        try:
                            # AT2/VT2/DT2 ayrımını format_type üzerinden yap
                            fmt = str(result_data.get('format_type', '')).upper()
                            if fmt == 'VT2':
                                kind = 'velocity'
                            elif fmt == 'DT2':
                                kind = 'displacement'
                            else:
                                kind = 'acceleration'
                            data_array = self._convert_units_array(kind, data_array, src_code, target_unit)
                        except Exception:
                            pass
                else:
                    data_array = np.asarray(result_data, dtype=float)
                    
            elif self._is_esm_format(lines):
                # ESM formatı - satır satır, soldan sağa oku
                print(f"📊 ESM formatı tespit edildi: {file_path}")
                result_data = self._parse_esm_format(lines, scaling_factor)
                if isinstance(result_data, dict):
                    data_array = np.asarray(result_data['acceleration'], dtype=float)
                    src_code = getattr(self, '_units_code', None)
                    if src_code:
                        try:
                            data_array = self._convert_units_array('acceleration', data_array, src_code, target_unit)
                        except Exception:
                            pass
                else:
                    data_array = np.asarray(result_data, dtype=float)
                    
            else:
                # Diğer formatlar için standart parsing (sütun bazlı)
                print(f"📊 Standart format tespit edildi: {file_path}")
                first_line = int(params.get('first_line', 6)) - 1
                last_line = int(params.get('last_line', -1))
                format_type = params.get('format', 'single_accel')
                accel_column = int(params.get('accel_column', 2)) - 1
                time_column = int(params.get('time_column', 1)) - 1
                frequency = int(params.get('frequency', 1))
                initial_skip = int(params.get('initial_skip', 0))

                data_lines = lines[first_line:] if last_line == -1 else lines[first_line:last_line]

                # Veriyi parse et (ivme parsing fonksiyonunu kullan)
                data_dict = self._parse_acceleration_data(
                    data_lines, format_type, accel_column, time_column,
                    frequency, initial_skip, scaling_factor
                )
                data_array = np.asarray(data_dict['acceleration'], dtype=float)
                # Format ivme ise ivme birimi üzerinden normalize et
                src_code = getattr(self, '_units_code', None)
                if src_code:
                    try:
                        data_array = self._convert_units_array('acceleration', data_array, src_code, target_unit)
                    except Exception:
                        pass
            
            print(f"✅ Ek dosya yüklendi: {len(data_array)} veri noktası")
            return data_array

        except Exception as e:
            print(f"❌ Ek dosya yükleme hatası: {e}")
            raise ValueError(f"Ek dosya yüklenemedi: {str(e)}") 
